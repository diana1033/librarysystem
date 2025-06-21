from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from librarian.models import User
from librarian.models import Book, Inventory
from librarian.serializers import BookIssueSerializer


class BookIssueSerializerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = User.objects.create_user(username='reader1', role='reader', password='123')
        cls.librarian = User.objects.create_user(username='lib1', role='librarian', password='123')
        cls.book = Book.objects.create(title='Test Book', count=1)
        cls.inventory = Inventory.objects.create(book=cls.book, status='available')

    def test_create_book_issue_success(self):
        data = {
            'reader_id': self.reader.id,
            'book_id': self.book.id
        }
        context = {'request': type('Request', (), {'user': self.librarian})()}

        serializer = BookIssueSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        issue = serializer.save()

        self.assertEqual(issue.reader, self.reader)
        self.assertEqual(issue.inventory.book, self.book)
        self.assertEqual(issue.issued_by, self.librarian)
        self.assertEqual(issue.inventory.status, 'borrowed')
        self.assertEqual(issue.due_date, timezone.now().date() + timedelta(days=30))
