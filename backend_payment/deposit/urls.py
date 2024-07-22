from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from deposit import views

app_name = 'deposit'

urlpatterns = [

    path('sms/', views.sms, name='sms'),
    path('create_copy_screen/', views.create_copy_screen, name='create_copy_screen'),
    # path('sms_forwarder/', views.sms_forwarder, name='sms_forwarder'),
    path('incomings/', views.IncomingListView.as_view(), name='incomings'),
    path('incomings/<int:pk>/', views.IncomingEdit.as_view(), name='incoming_edit'),
    path('trash/', views.IncomingTrashList.as_view(), name='trash'),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
