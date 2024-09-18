from django.shortcuts import render
from rest_framework.decorators import api_view


@api_view(["GET"])
def home_view(request):
    return render(request, "index.html")
