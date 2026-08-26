print("--- DEBUG: Loading myapp/urls.py ---") 
from django.urls import path, re_path, include

from . import views
from myapp import views
from django.contrib.auth import views as auth_views
from django.urls import path


urlpatterns = [

    
    path('',views.login),
    path('login/',views.login, name='login'),
    path('login_post/',views.login_post, name='login_post'),

    path('logout/', views.logout_view, name='logout_view'),

     ## path url for Detection Launcher----------------
    path('launch-detection-service/', views.launch_detection_service_launcher, name='launch_service_launcher_view'), # Renamed to avoid clash if needed
    path('prepare-launcher/camera/<int:camera_pk>/', views.prepare_launcher_for_camera, name='prepare_launcher_for_camera'),
    path('prepare-launcher/report-image/<int:report_pk>/', views.prepare_launcher_for_report_image, name='prepare_launcher_for_report_image'),



    path('admin_home/', views.admin_home, name='admin_home'),

    path('division/check-field/', views.admin_check_field_exists, name='admin_check_field_exists'), # New generic URL

    path('admin_add_forest_divition/', views.admin_add_forest_divition, name='admin_add_forest_divition'),
    path('admin_add_forest_divition_post', views.admin_add_forest_divition_post, name='admin_add_forest_divition_post'),

    path('division/check-name/', views.admin_check_division_name, name='admin_check_division_name'),
    path('division/check-place/', views.admin_check_division_place, name='admin_check_division_place'),

    path('admin_view_forest_divition/', views.admin_view_forest_divition, name='admin_view_forest_divition'),
    path('admin_edit_forest_divition/<int:id>/', views.admin_edit_forest_divition, name='admin_edit_forest_divition'),
    path('admin_delete_forest_divition/<int:id>/', views.admin_delete_forest_divition,
         name='admin_delete_forest_divition'),



    path('admin_add_forest_station/', views.admin_add_forest_station, name='admin_add_forest_station'),
    path('admin_add_forest_station_post', views.admin_add_forest_station_post, name='admin_add_forest_station_post'),
    path('admin_view_forest_station/', views.admin_view_forest_station, name='admin_view_forest_station'),
    path('admin_edit_forest_station/<int:id>/', views.admin_edit_forest_station,
         name='admin_edit_forest_station'),
    path('admin_delete_forest_station/<int:id>/', views.admin_delete_forest_station,
         name='admin_delete_forest_station'),



    path('admin_add_forest_officer/', views.admin_add_forest_officer, name='admin_add_forest_officer'),
    path('admin_add_forest_officer_post', views.admin_add_forest_officer_post, name='admin_add_forest_officer_post'),
    path('admin_view_forest_officer/', views.admin_view_forest_officer, name='admin_view_forest_officer'),
    path('admin_edit_forest_officer/<int:id>/', views.admin_edit_forest_officer,
         name='admin_edit_forest_officer'),
    path('admin_delete_forest_officer/<int:id>/', views.admin_delete_forest_officer,
         name='admin_delete_forest_officer'),

    path('check_username_exists/', views.check_username_exists, name='check_username_exists'),
    path('check_email_exists/', views.check_email_exists, name='check_email_exists'),    # NEW
    path('check_phone_exists/', views.check_phone_exists, name='check_phone_exists'), 

    path('admin_add_contacts/', views.admin_add_contacts, name='admin_add_contacts'),
    path('check_phone_exists_contact/', views.check_phone_exists_contact, name='check_phone_exists_contact'),


    path('admin_add_contacts_post', views.admin_add_contacts_post, name='admin_add_contacts_post'),
    path('admin_view_contacts/', views.admin_view_contacts, name='admin_view_contacts'),
    path('admin_edit_contacts/<int:id>/', views.admin_edit_contacts,
         name='admin_edit_contacts'),
    path('admin_delete_contacts/<int:id>/', views.admin_delete_contacts,
         name='admin_delete_contacts'),



#FEEDBACK
    path('admin_view_user_feedback/', views.admin_view_user_feedback, name='admin_view_user_feedback'),
    # New URL pattern for viewing a single feedback detail
    # <int:feedback_id> captures an integer from the URL and passes it to the view
    path('admin_view_user_feedback/<int:feedback_id>/', views.admin_feedback_detail, name='admin_feedback_detail'),
    path('admin_delete_user_feedback/<int:id>/', views.admin_delete_user_feedback,
         name='admin_delete_user_feedback'),

#FEEDBACK-----------ends here-------------------------------------#


    path('admin_send_notification_to_officer/', views.admin_send_notification_to_officer, name='admin_send_notification_to_officer'),
    path('admin_send_notification_to_officer_post/', views.admin_send_notification_to_officer_post, name='admin_send_notification_to_officer_post'),
    path('admin_view_notification_to_officer/', views.admin_view_notification_to_officer, name='admin_view_notification_to_officer'),
    # path('admin_edit_notification_to_officer/<int:id>/', views.admin_edit_notification_to_officer,
    #      name='admin_edit_notification_to_officer'),
    path('admin_delete_notification_to_officer/<int:id>/', views.admin_delete_notification_to_officer,
         name='admin_delete_notification_to_officer'),


    path('admin_view_officer_report/', views.admin_view_officer_report, name='admin_view_officer_report'),
    path('admin_delete_officer_report/<int:id>/', views.admin_delete_officer_report,
         name='admin_delete_officer_report'),





    path('admin_add_animal/', views.admin_add_animal, name='admin_add_animal'),
    path('check_animal_exists/', views.check_animal_exists, name='check_animal_exists'),

    
    path('admin_add_animal_post', views.admin_add_animal_post, name='admin_add_animal_post'),
    path('admin_view_animal/', views.admin_view_animal, name='admin_view_animal'),
    path('admin_edit_/<int:id>/', views.admin_edit_animal,
         name='admin_edit_animal'),
    path('admin_delete_animal/<int:id>/', views.admin_delete_animal,
         name='admin_delete_animal'),


# urls for admins to add camera incase that feature is needed
    path('admin_add_camera/', views.admin_add_camera),
    path('admin_add_camera_post', views.admin_add_camera_post),
    path('admin_view_camera/', views.admin_view_camera),
    path('admin_edit_camera/<int:id>/', views.admin_edit_camera,
         name='admin_edit_camera'),
    path('admin_delete_camera/<int:id>/', views.admin_delete_camera,
         name='admin_delete_camera'),


    path('admin_add_camera_alerts/', views.admin_add_camera_alerts),
    path('admin_add_camera_alerts_post', views.admin_add_camera_alerts_post),
    path('admin_view_camera_alerts/', views.admin_view_camera_alerts, name='admin_view_camera_alerts'),
    path('admin_edit_camera_alerts/<int:id>/', views.admin_edit_camera_alerts,
         name='admin_edit_camera_alerts'),
    path('admin_delete_camera_alerts/<int:id>/', views.admin_delete_camera_alerts,
         name='admin_delete_camera_alerts'),
    # New URL pattern for bulk delete
    path('admin_bulk_delete_camera_alerts/', views.admin_bulk_delete_camera_alerts,
         name='admin_bulk_delete_camera_alerts'),


    path('admin_add_dangerous_area/', views.admin_add_dangerous_area),




# Forest Officer URLs-------------------------------------------------------------------------------------------------------

    path('forest_officer_home/', views.forest_officer_home, name='forest_officer_home'),
    
    path('officer/profile/', views.view_officer_profile, name='view_officer_profile'),
    path('officer/profile/edit/', views.edit_officer_profile, name='edit_officer_profile'),

    path('change-password/', views.forest_officer_change_password, name='forest_officer_change_password'),

    path('officer/forgot-password/', views.officer_forgot_password_request, name='officer_forgot_password_request'),
    path('officer/reset-password/<uuid:token>/', views.officer_reset_password_confirm, name='officer_reset_password_confirm'),


    path('manage_dangerous_area_map/', views.manage_dangerous_area_map, name='manage_dangerous_area_map'),
    path('public_dangerous_area_map/', views.public_dangerous_area_map, name='public_dangerous_area_map'),

    # NEW: Trekking Request Management for Officers (Web)
    path('officer/trekking-requests/', views.officer_trekking_requests_list, name='officer_trekking_requests_list'),
    path('officer/trekking-requests/<int:pk>/', views.officer_trekking_request_detail, name='officer_trekking_request_detail'),


    # Native Django AI Detection Center URLs
    path('officer/detection-center/', views.forest_officer_detection_center, name='forest_officer_detection_center'),
    path('officer/detection-center/start/', views.start_detection_process_view, name='start_detection_process_view'),
    path('officer/detection-center/stop/<int:camera_id>/', views.stop_detection_process_view, name='stop_detection_process_view'),
    path('ajax/detection-status/', views.ajax_detection_status, name='ajax_detection_status'),

    path('forest_officer_add_camera/', views.forest_officer_add_camera, name='forest_officer_add_camera'),
    path('forest_officer_add_camera_post', views.forest_officer_add_camera_post, name='forest_officer_add_camera_post'),

    path('forest_officer_view_camera/', views.forest_officer_view_camera, name='forest_officer_view_camera'),
    path('forest_officer_edit_camera/<int:id>/', views.forest_officer_edit_camera,
         name='forest_officer_edit_camera'),
    path('forest_officer_delete_camera/<int:id>/', views.forest_officer_delete_camera,
         name='forest_officer_delete_camera'),

    path('view_my_webcam/', views.view_my_webcam, name='view_my_webcam'),




    path('forest_officer_add_camera_alerts/', views.forest_officer_add_camera_alerts, name='forest_officer_add_camera_alerts'),
    path('forest_officer_add_camera_alerts_post', views.forest_officer_add_camera_alerts_post, name='forest_officer_add_camera_alerts_post'),
    path('forest_officer_view_camera_alerts/', views.forest_officer_view_camera_alerts, name='forest_officer_view_camera_alerts'),
    path('forest_officer_edit_camera_alerts/<int:id>/', views.forest_officer_edit_camera_alerts,
         name='forest_officer_edit_camera_alerts'),
    path('forest_officer_delete_camera_alerts/<int:id>/', views.forest_officer_delete_camera_alerts,
         name='forest_officer_delete_camera_alerts'),
    # New URL pattern for bulk delete
    path('forest_officer_bulk_delete_camera_alerts/', views.forest_officer_bulk_delete_camera_alerts,
         name='forest_officer_bulk_delete_camera_alerts'),


    # New User Complaint URLs
    path('forest_officer_view_user_complaints/', views.forest_officer_view_user_complaints, name='forest_officer_view_user_complaints'),
    path('forest_officer_send_reply_to_user/<int:complaint_id>/', views.forest_officer_send_reply_to_user, name='forest_officer_send_reply_to_user'),
    # Corrected URL pattern for edit
    path('forest_officer_edit_reply_to_user/<int:complaint_id>/', views.forest_officer_edit_reply_to_user, name='forest_officer_edit_reply_to_user'),
    path('forest_officer_delete_reply_to_user/<int:complaint_id>/', views.forest_officer_delete_reply_to_user, name='forest_officer_delete_reply_to_user'),


    # New Alert to User URLs

    path('forest_officer_view_alert_to_user/', views.forest_officer_view_alert_to_user,
         name='forest_officer_view_alert_to_user'),
    # Add alert_id parameter for edit and delete
    path('ajax/get-camera-alert-details/<int:alert_id>/', views.get_camera_alert_details_json, name='ajax_get_camera_alert_details'),

    path('forest_officer_edit_alert_to_user/<int:alert_id>/', views.forest_officer_edit_alert_to_user,
         name='forest_officer_edit_alert_to_user'),
    path('forest_officer_delete_alert_to_user/<int:alert_id>/', views.forest_officer_delete_alert_to_user,
         name='forest_officer_delete_alert_to_user'),

    # --- API URLs for Android App ---

    path('forest_officer_view_curfew/', views.forest_officer_view_curfew, name='forest_officer_view_curfew'),
    path('forest_officer_send_curfew/', views.forest_officer_send_curfew, name='forest_officer_send_curfew'),
    path('forest_officer_send_curfew_post/', views.forest_officer_send_curfew_post, name='forest_officer_send_curfew_post'),

    path('forest_officer_edit_curfew/<int:curfew_id>/', views.forest_officer_edit_curfew, name='forest_officer_edit_curfew'),
    path('forest_officer_delete_curfew/<int:curfew_id>/', views.forest_officer_delete_curfew, name='forest_officer_delete_curfew'),


    # User Report URLs-------------------------------#

    path('forest_officer_view_user_report/', views.forest_officer_view_user_report, name='forest_officer_view_user_report'),

    # New URL for updating report status
    # Using re_path to capture the status string which includes underscores
    re_path(r'^forest_officer_update_report_status/(?P<report_id>\d+)/(?P<new_status>[a-z_]+)/$', views.forest_officer_update_report_status, name='forest_officer_update_report_status'),

   
    path('forest_officer_edit_user_report/<int:report_id>/', views.forest_officer_edit_user_report, name='forest_officer_edit_user_report'),
    path('forest_officer_delete_user_report/<int:report_id>/', views.forest_officer_delete_user_report, name='forest_officer_delete_user_report'),


# User Report urls-------ends here---------------------------######

    path('forest_officer_view_notification/', views.forest_officer_view_notification, name='forest_officer_view_notification'),



    path('forest_officer_send_report_to_admin/', views.forest_officer_send_report_to_admin),

    path('forest_officer_view_admin_notification/', views.forest_officer_view_admin_notification),
    path('forest_officer_view_alert_to_user/', views.forest_officer_view_alert_to_user),
   
    path('forest_officer_view_dangerous_spot/', views.forest_officer_view_dangerous_spot),
    path('forest_officer_view_trekking_requests/', views.forest_officer_view_trekking_requests),
    path('forest_officer_view_user_complaints/', views.forest_officer_view_user_complaints),


    # Forest Officer Tech Support URLs
    path('officer/request-tech-support/', views.forest_officer_request_tech_support, name='forest_officer_request_tech_support'),
    path('officer/view-tech-support-requests/', views.forest_officer_view_tech_support_requests, name='forest_officer_view_tech_support_requests'),

    # Admin Tech Support URLs
    path('tech-support-requests/', views.admin_view_tech_support_requests, name='admin_view_tech_support_requests'),
    path('tech-support-requests/update/<int:request_id>/', views.admin_update_tech_support_status, name='admin_update_tech_support_status'),



    path('safety-tips/add/', views.admin_add_safety_tip, name='admin_add_safety_tip'),
    path('safety-tips/add/post/', views.admin_add_safety_tip_post, name='admin_add_safety_tip_post'),
    path('safety-tips/view/', views.admin_view_safety_tips, name='admin_view_safety_tips'),
    path('safety-tips/edit/<int:id>/', views.admin_edit_safety_tip, name='admin_edit_safety_tip'),
    path('safety-tips/delete/<int:id>/', views.admin_delete_safety_tip, name='admin_delete_safety_tip'),


    # Web endpoint for users to confirm password reset via email link
    # This should *not* be under /api/ but directly accessible
    path('reset_password/<int:user_id>/<str:token>/', views.reset_password_confirm, name='password_reset_confirm_web'),




]
