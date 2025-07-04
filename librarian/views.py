from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, generics, status, filters
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from .permissions import IsLibrarian, IsReader, IsOwnerOrLibrarian
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models




from .models import User, Author, Direction, Publisher, Book, Inventory, BookIssue, BookReturn
from .serializers import (
    UserSerializer, RegisterSerializer,
    AuthorSerializer, DirectionSerializer,
    PublisherSerializer, BookSerializer,
    InventorySerializer, BookIssueSerializer, BookReturnSerializer
)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'passport', 'phone', 'username']
    filterset_fields = ['role']
    ordering_fields = ['last_name', 'username']

    def get_permissions(self):
        return [IsLibrarian()]


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name']
    ordering_fields = ['last_name', 'first_name']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsLibrarian()]


class DirectionViewSet(viewsets.ModelViewSet):
    queryset = Direction.objects.all()
    serializer_class = DirectionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsLibrarian()]


class PublisherViewSet(viewsets.ModelViewSet):
    queryset = Publisher.objects.all()
    serializer_class = PublisherSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsLibrarian()]



class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['publisher', 'direction']
    search_fields = ['title', 'authors__last_name']
    ordering_fields = ['title', 'quantity']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsLibrarian()]

    def destroy(self, request, *args, **kwargs):
        book = self.get_object()
        if Inventory.objects.filter(book=book, status='issued').exists():
            raise ValidationError("Нельзя удалить книгу, которая выдана.")
        book.is_active = False
        book.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InventoryViewSet(viewsets.ModelViewSet):
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['book', 'status']
    search_fields = ['inventory_number', 'book__title']
    ordering_fields = ['inventory_number']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsLibrarian()]


class BookIssueViewSet(viewsets.ModelViewSet):
    queryset = BookIssue.objects.select_related('reader', 'inventory', 'issued_by')
    serializer_class = BookIssueSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['reader', 'issued_by']
    search_fields = ['reader__last_name', 'inventory__inventory_number']
    ordering_fields = ['issue_date', 'due_date']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsLibrarian()]
        elif self.action == 'retrieve':
            return [IsOwnerOrLibrarian()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(issued_by=self.request.user)


class BookReturnViewSet(viewsets.ModelViewSet):
    queryset = BookReturn.objects.select_related('issue', 'issue__inventory', 'received_by')
    serializer_class = BookReturnSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['received_by']
    search_fields = ['issue__reader__last_name', 'issue__inventory__inventory_number']
    ordering_fields = ['return_date']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsLibrarian()]
        elif self.action == 'retrieve':
            return [IsOwnerOrLibrarian()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(received_by=self.request.user)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class IssuedBooksReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        issues = BookIssue.objects.select_related('reader', 'inventory__book', 'issued_by')

        report_data = []
        for issue in issues:
            returned = BookReturn.objects.filter(issue=issue).exists()
            status = "Возвращена" if returned else "На руках"
            report_data.append({
                "issue_id": issue.id,
                "issue_date": issue.issue_date,
                "title": issue.inventory.book.title,
                "reader": issue.reader.get_full_name(),
                "issued_by": issue.issued_by.get_full_name() if issue.issued_by else "-",
                "due_date": issue.due_date,
                "status": status,
            })

        return Response(report_data)

class OverdueBooksReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        overdue_issues = BookIssue.objects.filter(
            due_date__lt=today,
            inventory__status='issued'
        ).select_related('reader', 'inventory')

        data = []
        for issue in overdue_issues:
            data.append({
                'reader': str(issue.reader),
                'inventory_number': issue.inventory.inventory_number,
                'book_title': issue.inventory.book.title,
                'issue_date': issue.issue_date,
                'due_date': issue.due_date,
                'days_overdue': (today - issue.due_date).days,
            })

        return Response(data)


class BookAvailabilityReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        books = Book.objects.filter(is_deleted=False)

        report = []
        for book in books:
            total_copies = Inventory.objects.filter(book=book).count()
            available_copies = Inventory.objects.filter(book=book, status='available').count()
            issued_copies = Inventory.objects.filter(book=book, status='borrowed').count()
            deleted_copies = Inventory.objects.filter(book=book, status='deleted').count()

            report.append({
                'book_title': book.title,
                'total_copies': total_copies,
                'available_copies': available_copies,
                'issued_copies': issued_copies,
                'deleted_copies': deleted_copies,
            })

        return Response(report)

class ReaderActivityReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        readers = User.objects.filter(role='reader', is_active = True)

        report = []
        for reader in readers:
            books_borrowed = BookIssue.objects.filter(reader=reader).count()
            total_fines = BookReturn.objects.filter(issue__reader=reader).aggregate(
                total_fine=models.Sum('fine')
            )['total_fine'] or 0

            report.append({
                'reader_name': f"{reader.last_name} {reader.first_name}",
                'books_borrowed': books_borrowed,
                'total_fines': float(total_fines),
            })

        return Response(report)

# class ReaderAPIList(generics.ListCreateAPIView):
#     queryset = Reader.objects.all()
#     serializer_class = ReaderSerializer
#
# class ReaderAPIDetail(generics.RetrieveUpdateDestroyAPIView):
#     queryset = Reader.objects.all()
#     serializer_class = ReaderSerializer

# class ReaderAPIView(APIView):
#     def get(self, request):
#         r = Reader.objects.all()
#         return Response({'posts': ReaderSerializer(r, many=True).data})
#
#
#     def post(self, request):
#         serializer = ReaderSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#
#         return Response({'post': serializer.data})
#
#
#     def put(self, request, *args, **kwargs):
#         pk = kwargs.get("pk", None)
#         if not pk:
#             return Response({"error": "Method PUT not allowed"})
#
#         try:
#             instance = Reader.objects.get(pk = pk)
#         except:
#             return Response({"error": "Object does not exist"})
#
#
#         serializer = ReaderSerializer(data=request.data, instance=instance, partial=True)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response({"post": serializer.data})
#
#
#     def delete(self, request, *args, **kwargs):
#         pk = kwargs.get("pk", None)
#         if not pk:
#             return Response({"error": "Method DELETE not allowed"}, status=400)
#
#         try:
#             instance = Reader.objects.get(pk=pk)
#         except Reader.DoesNotExist:
#             return Response({"error": "Object does not exist"}, status=404)
#
#         instance.delete()
#         return Response({"message": "Reader deleted successfully"}, status=204)
