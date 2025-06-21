
# Create your models here.

from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import re

# Абстрактная модель мягкого удаления
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # если надо видеть всё (например, в админке)

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()


class User(AbstractUser):
    ROLE_CHOICES = [
        ('reader', 'Читатель'),
        ('librarian', 'Библиотекарь'),
    ]

    middle_name = models.CharField(max_length=50, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    passport = models.CharField(max_length=50, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='reader')

    def __str__(self):
        return f"{self.last_name} {self.first_name[0]}.{self.middle_name[0] if self.middle_name else ''}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save()


# --- Автор ---
class Author(SoftDeleteModel):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.last_name} {self.first_name[0]}.{self.middle_name[0] if self.middle_name else ''}"

# --- Направление (категория книги) ---
class Direction(SoftDeleteModel):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

# --- Издательство ---
class Publisher(SoftDeleteModel):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name

# --- Книга ---
class Book(SoftDeleteModel):
    CATEGORY_CHOICES = [
        ('textbook', 'Учебник'),
        ('manual', 'Методичка'),
        ('fiction', 'Художественная'),
        ('science', 'Научная'),
        ('', ' Публицистика'),
        ('other', 'Другое'),
    ]
    title = models.CharField(max_length=255)
    authors = models.ManyToManyField(Author)
    direction = models.ForeignKey(Direction, on_delete=models.SET_NULL, null=True)
    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True)
    udc = models.CharField("УДК", max_length=50, blank=True)  # УДК — строка, чтобы поддерживать формат вроде "004.4"
    bbk = models.CharField("ББК", max_length=50, blank=True)  # ББК — аналогично
    isbn = models.CharField("ISBN", max_length=20, blank=True)
    quantity = models.PositiveIntegerField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        creating = not self.pk
        old_quantity = None
        if not creating:
            old_quantity = Book.objects.get(pk=self.pk).quantity

        super().save(*args, **kwargs)

        # Если создается новая книга, создаем экземпляры
        if creating:
            for _ in range(self.quantity):
                # Сохраняем каждый экземпляр отдельно, чтобы сработал save()
                inventory_item = Inventory(book=self, status='available')
                inventory_item.save()

        elif old_quantity is not None:
            diff = self.quantity - old_quantity
            # Если количество увеличилось
            if diff > 0:
                for _ in range(diff):
                    inventory_item = Inventory(book=self, status='available')
                    inventory_item.save()

            # Если количество уменьшилось
            elif diff < 0:
                available = Inventory.objects.filter(
                    book=self,
                    status='available'
                )[:abs(diff)]
                if available.count() < abs(diff):
                    raise ValidationError(
                        "Нельзя уменьшить количество: недостаточно свободных экземпляров."
                    )
                for inv in available:
                    inv.update(status='deleted')

    def delete(self, *args, **kwargs):
        if BookIssue.objects.filter(book=self).exists():
            raise ValidationError("Нельзя удалить книгу, которая уже была выдана.")

        Inventory.objects.filter(book=self).update(status='deleted')
        self.is_deleted = True
        self.save()

class Inventory(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    inventory_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=[('available', 'Available'), ('borrowed', 'Borrowed'), ('deleted', 'Deleted')], default='available')

    def save(self, *args, **kwargs):
        if not self.inventory_number:
            super().save(*args, **kwargs)  # сначала сохранить, чтобы появился id
            self.inventory_number = f"INV-{self.id:05d}"
            return super().save(update_fields=["inventory_number"])
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if BookIssue.objects.filter(invantory=self).exists():
            raise ValidationError("Нельзя удалить книгу, которая уже была выдана.")

        self.status = "deleted"
        self.save()

    def __str__(self):
        return f"{self.inventory_number} — {self.book.title}"

class BookIssue(SoftDeleteModel):
    reader = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'reader'})
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_books',
                                  limit_choices_to={'role': 'librarian'})

    def __str__(self):
        return f"{self.reader} - {self.inventory}"



class BookReturn(SoftDeleteModel):
    issue = models.OneToOneField(BookIssue, on_delete=models.CASCADE)
    return_date = models.DateField(auto_now_add=True)
    condition = models.TextField(blank=True)
    fine = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='returned_books',
                                    limit_choices_to={'role': 'librarian'})

    def save(self, *args, **kwargs):
        if self.issue:
            due_date = self.issue.due_date
            now = timezone.now().date()
            if now > due_date:
                days_late = (now - due_date).days
                self.fine = days_late * 5  # 5 сомов в день
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Return for {self.issue}"


