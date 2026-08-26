# myapp/api_urls.py (for API Views)
from django.urls import path, include
from . import views # Assuming your API views are in myapp/views.py
from .views import AlertListView, EmergencyContactListView 
from rest_framework.routers import DefaultRouter
from .views import DangerousAreaViewSet, ForestStationViewSet, TrekkingRequestViewSet, TrekkingPassViewSet # Import your new ViewSet

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'dangerous-areas', DangerousAreaViewSet)
# NEW: Register the ForestStationViewSet
router.register(r'forest-stations', ForestStationViewSet, basename='forest-station')
router.register(r'trekking-requests', TrekkingRequestViewSet) # NEW
router.register(r'trekking-passes', TrekkingPassViewSet)     # NEW

urlpatterns = [
    # --- API URLs for Android App (accessible under /api/) ---
    # These paths do NOT have the 'api/' prefix here
    path('login/', views.login_api, name='api_login'), # Accessible at /api/login/
    path('create_account/', views.create_account, name='create_account'), # New account creation URL

    # Include the router URLs for your API
    path('dangerous-areas/check-location/', views.check_dangerous_location, name='api_check_dangerous_location'),
    path('map-cameras/', views.get_map_cameras_api, name='api_get_map_cameras'),
    path('map-animal-alerts/', views.get_map_animal_alerts_api, name='api_get_map_animal_alerts'),
    path('', include(router.urls)),
    # Add any other API endpoints you might have here

    path('auth/user/', views.get_current_user_details_api, name='get_current_user_details'), #for fetching user's station for Animal Alerts Activity android

    path('user_profile/<int:user_id>/', views.get_user_profile_api, name='get_user_profile'),
    path('update_user_profile/', views.update_user_profile_api, name='update_user_profile'),
    path('check_username_exists_userapp/', views.check_username_exists_userapp, name='check_username_exists_userapp'),

    path('check_email_exists_userapp/', views.check_email_exists_userapp, name='check_email_exists_userapp'),
    path('check_phone_exists_userapp/', views.check_phone_exists_userapp, name='check_phone_exists_userapp'),


    

    path('change_username/', views.change_username_api, name='change_username_api'),
    path('change_password/', views.change_password_api, name='change_password_api'),

    # API endpoint for Android app to request password reset email
    path('password_reset_request/', views.password_reset_request, name='api_password_reset_request'),

    path('forest_stations/', views.get_forest_stations, name='forest_stations_list'), # NEW URL

    path('get_officer_by_station/<int:station_id>/', views.get_officer_by_station, name='get_officer_by_station'), # NEW
    path('submit_complaint/', views.submit_complaint, name='submit_complaint'), # NEW
    path('user_my_complaints/<int:user_id>/', views.api_user_my_complaints, name='api_user_my_complaints'),
    path('delete_complaint/<int:complaint_id>/', views.delete_complaint, name='delete_complaint'),

    path('user_curfews/', views.api_user_view_curfews, name='api_user_view_curfews'),

    path('emergency-contacts/', EmergencyContactListView.as_view(), name='emergency-contact-list'),

    path('get_new_alerts/', views.api_get_new_alerts, name='api_get_new_alerts'), # Accessible at /api/get_new_alerts/
    path('get_all_user_alerts/', views.api_get_all_user_alerts, name='api_get_all_user_alerts'), # Accessible at /api/get_all_user_alerts/
    path('report_sighting/', views.report_sighting_api, name='api_report_sighting'), # Accessible at /api/report_sighting/
    path('sightings/', views.get_sightings_api, name='api_get_sightings'), # Accessible at /api/sightings/
    path('all_sightings/', views.get_all_sightings_api, name='api_all_sightings'),
    path('sightings/<int:sighting_id>/toggle_like/', views.toggle_like_sighting_api, name='api_toggle_like_sighting'),


    path('forest_stations/', views.get_forest_stations_api, name='api_get_forest_stations'), # Accessible at /api/forest_stations/
    path('feedback/', views.send_feedback_api, name='api_feedback'), # Accessible at /api/feedback/
    path('forest_officer_send_alert_to_user/', views.forest_officer_send_alert_to_user,
        name='forest_officer_send_alert_to_user'),

    path('alerts/', AlertListView.as_view(), name='alert-list'), # Add this line for the alerts endpoint
    path('alerts-trend/', views.alerts_trend_data, name='alerts_trend_data'), #this path is for alert trend chart in Officer homepage


        # --- API URLs for Android App ---
    # These URLs will be accessed by your Android application
    path('safety-tips/', views.api_list_safety_tips, name='api_list_safety_tips'),
    path('safety-tips/<int:pk>/', views.api_detail_safety_tip, name='api_detail_safety_tip'),

]
