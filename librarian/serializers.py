
from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from .models import Author, Direction, Publisher, Book, Inventory, BookIssue, BookReturn
from datetime import date
import re



User = get_user_model()

# --- User ---
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'middle_name', 'email',
                  'role', 'birth_date', 'passport', 'phone', 'address']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'passport': {'required': False},  # Делает паспорт необязательным при обновлении
            'phone': {'required': False},  # Делает телефон необязательным при обновлении
            'address': {'required': False},
        }

    def validate_passport(self, value):
        if not re.match(r'^[A-ZА-Я]{2}\d{6}$', value):
            raise serializers.ValidationError('Паспорт должен содержать 2 буквы и 6 цифр (например: AN123456)')
        return value

    def validate_phone(self, value):
        if not re.match(r'^\+996\d{9}$', value):
            raise serializers.ValidationError('Телефон должен быть в формате +996XXXXXXXXX')
        return value

    def validate_address(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError('Адрес слишком короткий')
        return value

    def validate_birth_date(self, value):
        if value and value > timezone.now().date():
            raise serializers.ValidationError('Дата рождения не может быть в будущем')
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)

        instance.save()
        return instance


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'first_name', 'last_name', 'middle_name', 'email',
                  'birth_date', 'passport', 'phone', 'address']

    def validate_birth_date(self, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 14:
            raise ValidationError("Регистрация разрешена только с 14 лет.")
        return value
    def validate_passport(self, value):
        if not re.match(r'^[A-ZА-Я]{2}\d{6}$', value):
            raise serializers.ValidationError('Паспорт должен содержать 2 буквы и 6 цифр (например: AN123456)')
        return value

    def validate_phone(self, value):
        if not re.match(r'^\+996\d{9}$', value):
            raise serializers.ValidationError('Телефон должен быть в формате +996XXXXXXXXX')
        return value

    def validate_address(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError('Адрес слишком короткий')
        return value

    def create(self, validated_data):
        validated_data['role'] = 'reader'
        return User.objects.create_user(**validated_data)


# --- Author ---
class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = '__all__'

# --- Direction ---
class DirectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direction
        fields = '__all__'

# --- Publisher ---
class PublisherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = '__all__'

# --- Book ---
class BookSerializer(serializers.ModelSerializer):
    authors = AuthorSerializer(many=True, read_only=True)
    direction = DirectionSerializer(read_only=True)
    publisher = PublisherSerializer(read_only=True)

    author_ids = serializers.PrimaryKeyRelatedField(
        queryset=Author.objects.filter(is_deleted=False), many=True, write_only=True
    )
    direction_id = serializers.PrimaryKeyRelatedField(
        queryset=Direction.objects.filter(is_deleted=False), write_only=True
    )
    publisher_id = serializers.PrimaryKeyRelatedField(
        queryset=Publisher.objects.filter(is_deleted=False), write_only=True
    )
    class Meta:
        model = Book
        fields = '__all__'

    def create(self, validated_data):
        author_ids = validated_data.pop('author_ids')
        direction = validated_data.pop('direction_id')
        publisher = validated_data.pop('publisher_id')

        book = Book(**validated_data, direction=direction, publisher=publisher)
        book.save()
        book.authors.set(author_ids)

        return book

    def update(self, instance, validated_data):
        author_ids = validated_data.pop('author_ids', None)
        direction = validated_data.pop('direction_id', None)
        publisher = validated_data.pop('publisher_id', None)

        if direction is not None:
            instance.direction = direction
        if publisher is not None:
            instance.publisher = publisher

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if author_ids is not None:
            instance.authors.set(author_ids)

        return instance



# --- Inventory ---
class InventorySerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)

    class Meta:
        model = Inventory
        fields = '__all__'



# --- BookIssue ---
class BookIssueSerializer(serializers.ModelSerializer):
    reader = UserSerializer(read_only=True)
    inventory = InventorySerializer(read_only=True)

    book_id = serializers.PrimaryKeyRelatedField(
        queryset=Book.objects.filter(is_deleted=False),
        write_only=True
    )
    reader_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='reader', is_active=True),
        write_only=True
    )

    class Meta:
        model = BookIssue
        fields = ['id', 'reader', 'reader_id', 'book_id', 'inventory', 'issued_by', 'issue_date', 'due_date']
        read_only_fields = ['issue_date', 'due_date', 'issued_by', 'reader', 'inventory']

    def validate(self, attrs):
        reader = attrs['reader_id']
        book = attrs['book_id']

        # Проверка: доступные экземпляры
        if not Inventory.objects.filter(book=book, status='available').exists():
            raise serializers.ValidationError("Нет доступных экземпляров этой книги.")

        # Проверка: больше 3 книг у пользователя
        active_issues = BookIssue.objects.filter(
            reader=reader,
            bookreturn__isnull=True
        )
        if active_issues.count() >= 3:
            raise serializers.ValidationError("Нельзя иметь больше 3 книг одновременно.")

        # Проверка: пользователь уже имеет эту книгу
        if active_issues.filter(inventory__book=book).exists():
            raise serializers.ValidationError("У пользователя уже есть эта книга на руках.")

        return attrs

    def create(self, validated_data):
        reader = validated_data.pop('reader_id')
        book = validated_data.pop('book_id')

        inventory = Inventory.objects.filter(book=book, status='available').first()
        validated_data['reader'] = reader
        validated_data['inventory'] = inventory
        validated_data['due_date'] = timezone.now().date() + timedelta(days=30)
        validated_data['issued_by'] = self.context['request'].user

        inventory.status = 'borrowed'
        inventory.save()

        return super().create(validated_data)

# --- BookReturn ---
class BookReturnSerializer(serializers.ModelSerializer):
    issue = BookIssueSerializer(read_only=True)
    issue_id = serializers.PrimaryKeyRelatedField(
        queryset=BookIssue.objects.all(),
        write_only=True
    )

    class Meta:
        model = BookReturn
        fields = ['id', 'issue', 'issue_id', 'return_date', 'condition', 'fine', 'received_by']
        read_only_fields = ['return_date', 'received_by', 'issue', 'fine']

    def validate_issue_id(self, value):
        if BookReturn.objects.filter(issue=value).exists():
            raise serializers.ValidationError("Эта книга уже была возвращена.")
        return value

    def create(self, validated_data):
        issue = validated_data.pop('issue_id')
        inventory = issue.inventory

        inventory.status = 'available'
        inventory.save()

        validated_data['issue'] = issue
        validated_data['received_by'] = self.context['request'].user

        return super().create(validated_data)
