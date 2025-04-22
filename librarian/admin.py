from django.contrib import admin
from django.contrib.admindocs.views import BookmarkletsView

from .models import  User,Author, Publisher, Direction,  Book, Inventory, BookIssue, BookReturn

# Register your models here.
admin.site.register(User)
admin.site.register(Book)
admin.site.register(Author)
admin.site.register(Publisher)
admin.site.register(Direction)
admin.site.register(Inventory)
admin.site.register(BookIssue)
admin.site.register(BookReturn)
