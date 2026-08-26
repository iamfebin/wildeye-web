from django.http import HttpResponse, FileResponse, Http404, HttpResponseRedirect
from django.contrib import messages # Import messages framework
from django.shortcuts import render, redirect, get_object_or_404 # Add get_object_or_404 here
from datetime import datetime, date # Import both date and datetime
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect
from django.db.models import Q #For multiple search term.
# Create your views here.
from myapp.models import *
import traceback
import os # <--- ADD THIS LINE
from django.conf import settings # Import settings for accessing MEDIA_ROOT

from django.shortcuts import render, redirect as django_redirect, get_object_or_404
from .forms import CameraAlertForm, CurfewInfoForm, ComplaintReplyForm, AlertToUserForm, UserUploadForm, CameraForm, CameraAlertEditForm, ComplaintFilterForm
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
import json
# from django.contrib.gis.geos import GEOSGeometry, GEOSException # Import GEOSGeometry
from django.contrib import messages # For messages framework
from django.core.serializers import serialize # Can also use this to serialize GeoJSON
from django.forms.models import model_to_dict # Useful if needed
from django.urls import reverse
from django.contrib.auth.hashers import make_password, check_password


# Example Regular User Registration View
from django.http import JsonResponse # For API registration
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from .models import RegularUserLogin, user_table # Import the new models
from django.contrib.auth.decorators import login_required

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import user_table, user_upload # Import user_upload model
# You might need date/time parsing utilities if you require specific formats
from datetime import datetime, date, time
import json # Might need if handling JSON body instead of POST data

from rest_framework import generics
from .models import alert_to_user
from .serializers import AlertSerializer, ForestStationSerializer, UserRegistrationSerializer, ForestStationSerializer, ForestOfficerSerializer, ComplaintSerializer, DangerousAreaSerializer, TrekkingRequestSerializer, TrekkingPassSerializer, ContactSerializer, CameraMapSerializer, CameraAlertMapSerializer
# from rest_framework.permissions import IsAuthenticated # Optional: Import permission class


from django.utils import timezone
from datetime import timedelta, date # Import date specifically
from django.db.models import Count

from django.views.decorators.cache import never_cache # Import this!
from functools import wraps

def role_required(*allowed_roles):
    """
    Decorator for views that checks if the user is authenticated
    and has one of the allowed roles stored in request.session['user_type'].
    Enforces @never_cache so browsers will not cache protected pages/forms in back-forward cache.
    """
    def decorator(view_func):
        @wraps(view_func)
        @never_cache
        def _wrapped_view(request, *args, **kwargs):
            if not request.session.get('is_authenticated'):
                return redirect(reverse('login'))
            user_type = request.session.get('user_type')
            if user_type not in allowed_roles:
                if user_type == 'admin':
                    return redirect(reverse('admin_home'))
                elif user_type == 'officer':
                    return redirect(reverse('forest_officer_home'))
                return redirect(reverse('login'))
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def admin_required(view_func):
    return role_required('admin')(view_func)

def officer_required(view_func):
    return role_required('officer')(view_func)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

import base64
from django.core.files.base import ContentFile
from rest_framework import status # ADD THIS LINE
from django.db import transaction # <--- ADD THIS LINE
from django.views.decorators.http import require_http_methods
from django.core.files.storage import FileSystemStorage
from django.db.models import Q, Max # ADD Max here

# Your existing imports for DRF and models
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action

from rest_framework.authentication import SessionAuthentication, BasicAuthentication # Import for authentication
from rest_framework.parsers import MultiPartParser, FormParser # For file uploads

from .pdf_utils import generate_trekking_pass_pdf # NEW: Import PDF utility
from rest_framework.pagination import PageNumberPagination # Import PageNumberPagination

from rest_framework.parsers import MultiPartParser, FormParser, JSONParser # Import JSONParser
from rest_framework.exceptions import PermissionDenied

from django.template.loader import render_to_string
from django.core.mail import send_mail

import re

from zoneinfo import ZoneInfo
from datetime import timezone as dt_timezone

from django.views.decorators.http import require_POST, require_GET

from rest_framework.exceptions import ParseError # Import ParseError


import subprocess
import sys

import urllib.parse # For URL encoding the image path


import logging
logger = logging.getLogger(__name__)



class AlertListView(generics.ListAPIView):
    """
    API View to list User Alerts.
    Orders by creation time, newest first.
    Optionally filters by 'station_id':
    - If 'station_id' is provided, shows alerts created by officers belonging to that station.
    - If 'station_id' is not provided, shows all alerts.
    """
    serializer_class = AlertSerializer # Ensure AlertSerializer is defined

    def get_queryset(self):
        # Base queryset with necessary select_related for performance
        queryset = alert_to_user.objects.select_related(
            'CAMERA_ALERT',
            'CAMERA_ALERT__ANIMAL', # For animal_name in CameraAlertSerializer
            'OFFICER',              # To access officer details
            'OFFICER__STATION'      # To access the officer's station for filtering
        ).all()

        station_id_filter = self.request.query_params.get('station_id', None)

        if station_id_filter:
            try:
                station_id = int(station_id_filter)
                # Filter for alerts where the creating OFFICER belongs to the specified station_id
                # The relationship is: alert_to_user -> OFFICER (ForeignKey to forest_officer) -> STATION (ForeignKey to forest_station)
                queryset = queryset.filter(OFFICER__STATION__id=station_id) # <--- MODIFIED FILTERING LOGIC
            except (ValueError, TypeError):
                # If station_id is provided but not a valid integer, it's a client error.
                raise ParseError("Query parameter 'station_id' must be an integer.")
            except Exception as e:
                # Log the error for debugging
                print(f"Error during alert filtering: {e}")
                # Depending on desired behavior, you might return an empty queryset or re-raise
                # For now, let's allow it to proceed which might return unfiltered or an error if the query becomes invalid
                pass

        return queryset.order_by('-created_at')


@csrf_exempt
def create_account(request):
    """
    Handles new user account creation.
    Expects JSON with full user details including username, password, station_id, and optional profile_image.
    """
    print("--- Debug: Entered create_account view ---")
    if request.method == 'POST':
        print("--- Debug: Received POST request for account creation ---")
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            place = data.get('place')
            pin = data.get('pin')
            phone = data.get('phone')
            email = data.get('email')
            station_id = data.get('station_id')
            profile_image_base64 = data.get('profile_image')

            print(f"--- Debug (Backend): Received data - Username: {username}, Email: {email}, Station ID: {station_id} ---")
            print(f"--- Debug (Backend): Profile Image Base64: {profile_image_base64 is not None}, Length: {len(profile_image_base64) if profile_image_base64 else 0} ---")

            # Basic validation for required fields
            if not all([username, password, first_name, last_name, place, pin, phone, email, station_id is not None]):
                print("--- Debug (Backend): Missing required fields (including station_id) ---")
                return JsonResponse({"success": False, "message": "All fields are required, including Forest Station."}, status=400)

            # Validate PIN and Phone are numeric
            if not (isinstance(pin, (int, str)) and str(pin).isdigit()) or \
               not (isinstance(phone, (int, str)) and str(phone).isdigit()):
                print("--- Debug (Backend): PIN or Phone is not numeric ---")
                return JsonResponse({"success": False, "message": "PIN and Phone must be numeric."}, status=400)

            # Password minimum length check
            if len(str(password)) < 6:
                print("--- Debug (Backend): Password too short ---")
                return JsonResponse({"success": False, "message": "Password must be at least 6 characters long."}, status=400)

            # Check if username already exists
            if RegularUserLogin.objects.filter(username__iexact=username).exists():
                print(f"--- Debug (Backend): Username '{username}' already exists ---")
                return JsonResponse({"success": False, "message": "Username already exists. Please choose a different one."}, status=409)

            # Check if email already exists
            if user_table.objects.filter(email__iexact=email).exists():
                print(f"--- Debug (Backend): Email '{email}' already exists ---")
                return JsonResponse({"success": False, "message": "Email address is already registered."}, status=409)

            # Check if phone already exists
            if user_table.objects.filter(phone=phone).exists():
                print(f"--- Debug (Backend): Phone '{phone}' already exists ---")
                return JsonResponse({"success": False, "message": "Phone number is already registered."}, status=409)

            # Use a transaction to ensure atomicity
            with transaction.atomic():
                # Retrieve the forest_station object based on station_id
                station = None
                try:
                    station = forest_station.objects.get(id=station_id)
                    print(f"--- Debug (Backend): Found forest_station with ID: {station_id}, Name: {station.name} ---")
                except forest_station.DoesNotExist:
                    print(f"--- Debug (Backend): Forest station with ID {station_id} does not exist ---")
                    return JsonResponse({"success": False, "message": "Invalid Forest Station selected."}, status=400)

                # Create RegularUserLogin instance and hash the password
                regular_login = RegularUserLogin(username=username)
                regular_login.set_password(password)
                regular_login.save()
                print(f"--- Debug (Backend): RegularUserLogin created for username '{username}' with ID: {regular_login.id} ---")

                # Handle profile image upload if provided
                image_file = None
                if profile_image_base64:
                    try:
                        img_data = base64.b64decode(profile_image_base64)
                        file_name = f"{username}_profile.jpg"
                        image_file = ContentFile(img_data, name=file_name)
                        print("--- Debug (Backend): Profile image decoded from Base64 to ContentFile successfully ---")
                    except Exception as e:
                        print(f"--- Error (Backend): Decoding profile image Base64 failed: {e} ---")
                        image_file = None

                # Create user_table instance
                user = user_table.objects.create(
                    REGULAR_LOGIN=regular_login,
                    STATION=station,
                    first_name=first_name,
                    last_name=last_name,
                    place=place,
                    pin=pin,
                    phone=phone,
                    email=email,
                    image=image_file
                )
                print(f"--- Debug (Backend): user_table profile created for '{username}' with ID: {user.id} ---")

            return JsonResponse({"success": True, "message": "Account created successfully."}, status=201)

        except json.JSONDecodeError:
            print("--- Debug (Backend): JSON Decode Error on account creation body ---")
            return JsonResponse({"success": False, "message": "Invalid JSON format in request body."}, status=400)
        except Exception as e:
            print(f"--- Fatal Error (Backend): During account creation: {e} ---")
            import traceback
            traceback.print_exc()
            return JsonResponse({"success": False, "message": f"An internal server error occurred: {str(e)}"}, status=500)

    else:
        print("--- Debug (Backend): Received non-POST request for account creation ---")
        return JsonResponse({"success": False, "message": "Only POST method allowed"}, status=405)


@csrf_exempt # Consider proper authentication/CSRF tokens in production for security
def login_api(request):
    print("--- Debug: Entered login_api view ---")

    if request.method == 'POST':
        print("--- Debug: Received POST request ---")

        username = None
        password = None

        # Prefer JSON body for API requests
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            print(f"--- Debug: Parsed JSON body - username: {username}, password: {password} ---")
        except json.JSONDecodeError:
            print("--- Debug: JSON Decode Error on body, trying request.POST (unlikely for Android app) ---")
            # Fallback to request.POST if JSON fails (less common for mobile APIs)
            username = request.POST.get('username')
            password = request.POST.get('password')
            print(f"--- Debug: Attempting with request.POST - username: {username}, password: {password} ---")
        except Exception as e:
            print(f"--- Debug: Error parsing request body: {e} ---")
            return JsonResponse({'success': False, 'message': 'Error parsing request body'}, status=400)


        # Ensure username and password were successfully retrieved
        if not username or not password:
            print("--- Debug: Username or password not found in request ---")
            return JsonResponse({'success': False, 'message': 'Username and password are required'}, status=400)


        # --- Authentication Logic ---
        user_id_to_return = None
        session_user_id = None
        user_type = None
        login_successful = False

        # 1. Attempt to authenticate as Regular User (Android App User)
        try:
            regular_login_obj = RegularUserLogin.objects.get(username=username)
            if regular_login_obj.check_password(password):
                user_id_to_return = regular_login_obj.id
                session_user_id = regular_login_obj.id
                user_type = 'regular_user'
                login_successful = True
                print(f"--- Debug: Regular User Login successful for {username}, ID: {user_id_to_return} ---")
            else:
                print(f"--- Debug: Regular user '{username}' password mismatch. ---")
        except RegularUserLogin.DoesNotExist:
            print(f"--- Debug: Regular user '{username}' not found. Trying as Officer/Admin. ---")
            pass

        # 2. If not a regular user, attempt to authenticate as Officer/Admin
        if not login_successful:
            try:
                officer_login_obj = login_table.objects.get(username__iexact=username)
                from django.contrib.auth.hashers import check_password, make_password
                is_valid = check_password(password, officer_login_obj.password)
                if not is_valid and officer_login_obj.password == password:
                    # Auto-upgrade legacy plaintext password to secure PBKDF2 hash
                    officer_login_obj.password = make_password(password)
                    officer_login_obj.save(update_fields=['password'])
                    is_valid = True

                if is_valid:
                    session_user_id = officer_login_obj.id  # Store login_table ID for session lookups
                    try:
                        officer_profile = forest_officer.objects.get(LOGIN=officer_login_obj)
                        user_id_to_return = officer_profile.id
                    except forest_officer.DoesNotExist:
                        user_id_to_return = officer_login_obj.id

                    user_type = officer_login_obj.type # e.g., 'officer', 'admin'
                    login_successful = True
                    print(f"--- Debug: Officer/Admin Login successful for {username}, Login ID: {session_user_id}, Type: {user_type} ---")
                else:
                    print(f"--- Debug: Officer/Admin '{username}' password mismatch. ---")
            except login_table.DoesNotExist:
                print(f"--- Debug: Officer/Admin '{username}' not found. ---")
                pass

        if login_successful:
            # Clear any existing session data to prevent session fixation
            request.session.flush()

            # Store necessary information in the session
            request.session['is_authenticated'] = True
            request.session['user_id'] = session_user_id
            request.session['user_type'] = user_type

            remember = False
            if isinstance(data, dict):
                remember = data.get('rememberMe') or data.get('remember_me')
            else:
                remember = request.POST.get('rememberMe') or request.POST.get('remember_me')

            if remember:
                request.session.set_expiry(1209600)  # 2 weeks (14 days)
            else:
                request.session.set_expiry(0)  # Expire when browser closes

            request.session.modified = True
            request.session.save()

            print(f"--- Debug: Session created/updated. Session ID: {request.session.session_key} ---")
            print(f"--- Debug: Session data: user_id={request.session.get('user_id')}, user_type={request.session.get('user_type')} ---")

            response = JsonResponse({
                'success': True,
                'message': 'Login successful',
                'user_id': user_id_to_return,
                'username': username,
                'user_type': user_type,
            })

            print("--- Debug: Login successful, returning response with Set-Cookie header ---")
            return response
        else:
            print("--- Debug: Login failed for both regular user and officer/admin ---")
            return JsonResponse({'success': False, 'message': 'Invalid username or password'}, status=401)

    else:
        # --- FAILURE PATH: Method Not Allowed ---
        print("--- Debug: Received non-POST request ---")
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'}, status=405)






def logout_view(request):
    # Clear the session data to log the user out
    request.session.flush()
    # Redirect to the login page
    return redirect(reverse('login'))


@never_cache
def login(request):
    # If user is already authenticated, redirect to their home dashboard
    if request.session.get('is_authenticated'):
        user_type = request.session.get('user_type')
        if user_type == 'admin':
            return redirect(reverse('admin_home'))
        elif user_type == 'officer':
            return redirect(reverse('forest_officer_home'))

    return render(request, 'index.html')

def login_post(request):
    if request.method == 'POST': # Ensure it's a POST request
        username = request.POST.get('username') # Use .get() for safety
        password = request.POST.get('password')

        # if not username or not password:
        #      # Basic validation
        #      return HttpResponse('''<script>alert("Please enter username and password");window.location='{}'</script>'''.format(reverse('login')))

        if not username or not password:
            messages.error(request, "Please enter username and password.")
            return redirect(reverse('login'))


        try:
            from django.contrib.auth.hashers import check_password, make_password
            ob = login_table.objects.get(username__iexact=username)

            is_valid = check_password(password, ob.password)
            if not is_valid and ob.password == password:
                # Auto-upgrade legacy plaintext password to secure PBKDF2 hash
                ob.password = make_password(password)
                ob.save(update_fields=['password'])
                is_valid = True

            if not is_valid:
                request.session.flush()
                messages.error(request, "Invalid username or password.")
                return redirect(reverse('login'))

            # Flush session to prevent Session Fixation
            request.session.flush()

            # Store user information in the session
            request.session['is_authenticated'] = True
            request.session['user_id'] = ob.id  # Store login_table ID
            request.session['user_type'] = ob.type

            if request.POST.get('rememberMe') or request.POST.get('remember_me'):
                request.session.set_expiry(1209600)  # 2 weeks (14 days)
            else:
                request.session.set_expiry(0)  # Expire when browser closes

            if ob.type == 'admin':
                messages.success(request, "Admin login successful.")
                return redirect(reverse('admin_home'))
            elif ob.type == "officer":
                messages.success(request, "Officer login successful.")
                return redirect(reverse('forest_officer_home'))
            else:
                request.session.flush()
                messages.error(request, "Unknown user role.")
                return redirect(reverse('login'))

        except login_table.DoesNotExist:
            request.session.flush()
            messages.error(request, "Invalid username or password.")
            return redirect(reverse('login'))

        except Exception as e:
            print(f"An error occurred during login: {e}")
            request.session.flush()
            messages.error(request, "An unexpected error occurred during login.")
            return redirect(reverse('login'))

    else:
        # Handle GET requests to login_post (e.g., direct access)
        return redirect(reverse('login'))

@never_cache
@admin_required
def admin_home(request):
    # --- Chart Data Preparation ---

    # 1. IT Support Requests Status (Pie Chart)
    status_counts = TechSupportRequest.objects.values('status').annotate(count=Count('id')).order_by('status')
    
    status_labels = []
    status_data = []
    status_display_names = dict(TechSupportRequest._meta.get_field('status').choices) # Get display names

    for item in status_counts:
        status_labels.append(status_display_names.get(item['status'], item['status'])) # Use display name
        status_data.append(item['count'])

    # 2. Hourly Requests Received (Line Chart for last 24 hours)
    now = timezone.now()
    
    # Determine the target timezone for display
    try:
        display_tz_str = getattr(settings, 'DISPLAY_TIME_ZONE', settings.TIME_ZONE)
        display_tz = ZoneInfo(display_tz_str)
    except Exception:
        display_tz = ZoneInfo(settings.TIME_ZONE) # Fallback to TIME_ZONE
        print(f"Warning: DISPLAY_TIME_ZONE setting is invalid or not found. Falling back to TIME_ZONE: {settings.TIME_ZONE}")

    # Convert 'now' to the display timezone for consistent boundary setting
    now_display_tz = now.astimezone(display_tz)

    start_of_24h_window_display_tz = (now_display_tz - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
    
    # For querying the database, we need the equivalent UTC time for this display window start
    # because database times are likely stored in UTC (due to USE_TZ=True)
    start_of_24h_window_utc = start_of_24h_window_display_tz.astimezone(dt_timezone.utc)


    requests_in_last_24h_qs = TechSupportRequest.objects.filter(
        request_date__gte=start_of_24h_window_utc, # Query using UTC boundary
        request_date__lte=now # 'now' is already UTC if from timezone.now()
    ).order_by('request_date')

    hourly_counts = {i: 0 for i in range(24)}
    hourly_labels_final = [""] * 24

    for i in range(24):
        # Calculate the hour slot start in the display timezone for the label
        hour_slot_start_display_tz = start_of_24h_window_display_tz + timedelta(hours=i)
        hourly_labels_final[i] = hour_slot_start_display_tz.strftime('%I %p')

    for req in requests_in_last_24h_qs:
        # Convert actual request_date (which is UTC from DB) to display timezone
        request_date_display_tz = req.request_date.astimezone(display_tz)
        
        # Normalize to its hour slot in the display timezone
        request_hour_slot_display_tz = request_date_display_tz.replace(minute=0, second=0, microsecond=0)

        if request_hour_slot_display_tz >= start_of_24h_window_display_tz:
            time_diff_seconds = (request_hour_slot_display_tz - start_of_24h_window_display_tz).total_seconds()
            hour_index = int(time_diff_seconds // 3600)

            if 0 <= hour_index < 24:
                hourly_counts[hour_index] += 1
            # else:
            #     print(f"Warning: Req {req.id} date {request_date_display_tz} slot {request_hour_slot_display_tz} idx {hour_index}")

    hourly_data_final = [hourly_counts[i] for i in range(24)]


    # Card counts
    total_officers = forest_officer.objects.count()
    total_stations = forest_station.objects.count()
    total_divisions = forest_division.objects.count()
    total_it_requests = TechSupportRequest.objects.filter(status='pending').count()

    context = {
        'status_labels_json': json.dumps(status_labels),
        'status_data_json': json.dumps(status_data),
        'hourly_received_labels_json': json.dumps(hourly_labels_final),
        'hourly_received_data_json': json.dumps(hourly_data_final),
        'card_officers_count': total_officers,
        'card_stations_count': total_stations,
        'card_divisions_count': total_divisions,
        'card_requests_count': total_it_requests,
    }

    # If checks pass, render the template
    return render(request, 'Admin/admin_home.html', context)






def officer_forgot_password_request(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        officer_instance = None

        if not identifier:
            return HttpResponse('''<script>alert("Please enter an email or username.");window.location='{}'</script>'''.format(reverse('officer_forgot_password_request')))

        try:
            # Try finding by email first (case-insensitive)
            officer_instance = forest_officer.objects.get(email__iexact=identifier)
        except forest_officer.DoesNotExist:
            try:
                # Try finding by username via login_table (case-insensitive)
                # Ensure it's an officer type
                login_entry = login_table.objects.get(username__iexact=identifier, type='officer')
                officer_instance = forest_officer.objects.get(LOGIN=login_entry)
            except (login_table.DoesNotExist, forest_officer.DoesNotExist):
                # Officer not found by either email or username
                # To avoid user enumeration, you might want to show a generic message here.
                # However, following the request to inform if not matched:
                return HttpResponse('''<script>alert("No officer account found matching that email or username.");window.location='{}'</script>'''.format(reverse('officer_forgot_password_request')))
        except forest_officer.MultipleObjectsReturned:
             # This case should ideally not happen if emails/usernames are unique for officers
             return HttpResponse('''<script>alert("Multiple accounts found. Please contact support.");window.location='{}'</script>'''.format(reverse('officer_forgot_password_request')))


        if officer_instance:
            if not officer_instance.email:
                return HttpResponse(f'''<script>alert("The officer account for '{officer_instance.first_name} {officer_instance.last_name}' does not have a registered email address. Cannot send reset link.");window.location='{reverse('officer_forgot_password_request')}'</script>''')

            # Invalidate any existing tokens for this officer to ensure only the latest one is valid
            OfficerPasswordResetToken.objects.filter(officer=officer_instance).delete()

            # Create new token
            reset_token = OfficerPasswordResetToken.objects.create(officer=officer_instance)
            
            # Build reset link
            # Ensure your site's domain is correctly configured for request.build_absolute_uri()
            # or hardcode if necessary for local development if request.build_absolute_uri gives 127.0.0.1:8000
            reset_link = request.build_absolute_uri(
                reverse('officer_reset_password_confirm', kwargs={'token': str(reset_token.token)})
            )
            
            # Send email
            subject = 'Password Reset Request for Your Officer Account'
            message = f"""
            Hello {officer_instance.first_name},

            A password reset was requested for your officer account.
            Please click the link below to set a new password:
            {reset_link}

            If you did not request this, please ignore this email.
            This link will expire in 1 hour.

            Thank you.
            """
            # Ensure DEFAULT_FROM_EMAIL is set in settings.py
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost')
            
            try:
                send_mail(subject, message, from_email, [officer_instance.email])
                # Generic success message to avoid confirming if an email exists, for better privacy
                return HttpResponse(f'''<script>alert("If an account exists for the provided identifier and has a registered email, a password reset link has been sent. Please check the inbox.");window.location='{reverse('login')}'</script>''')
            except Exception as e:
                print(f"Error sending password reset email: {e}") # Log this for debugging
                # Don't reveal specific email sending errors to the user for security
                return HttpResponse(f'''<script>alert("There was an issue processing your request. If the problem persists, please contact support.");window.location='{reverse('officer_forgot_password_request')}'</script>''')
        # This else should ideally not be reached if the above try-except covers all cases
        # but as a fallback:
        else:
            return HttpResponse('''<script>alert("No officer account found matching that email or username.");window.location='{}'</script>'''.format(reverse('officer_forgot_password_request')))

    return render(request, 'officer_forgot_password.html')


def officer_reset_password_confirm(request, token):
    try:
        reset_token_obj = OfficerPasswordResetToken.objects.get(token=token)
    except OfficerPasswordResetToken.DoesNotExist:
        return HttpResponse('''<script>alert("Invalid or expired password reset link. Please request a new one.");window.location='{}'</script>'''.format(reverse('officer_forgot_password_request')))

    if reset_token_obj.is_expired():
        reset_token_obj.delete() # Clean up expired token
        return HttpResponse('''<script>alert("Password reset link has expired. Please request a new one.");window.location='{}'</script>'''.format(reverse('officer_forgot_password_request')))

    officer_instance = reset_token_obj.officer
    login_entry = officer_instance.LOGIN # Get the related login_table entry

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or not confirm_password:
            context = {'token': token, 'error_message': 'Both password fields are required.'}
            return render(request, 'officer_reset_password_form.html', context)
        
        if new_password != confirm_password:
            context = {'token': token, 'error_message': 'Passwords do not match.'}
            return render(request, 'officer_reset_password_form.html', context)

        
        login_entry.password = make_password(new_password)
        login_entry.save()
    

        reset_token_obj.delete() # Invalidate the token after successful reset

        return HttpResponse('''<script>alert("Your password has been successfully reset. You can now login with your new password.");window.location='{}'</script>'''.format(reverse('login')))

    context = {'token': token}
    return render(request, 'officer_reset_password_form.html', context)

@never_cache
@officer_required
def forest_officer_home(request):
    """
    Displays the home dashboard for a logged-in forest officer.

    This view is designed to handle cases where an officer may not be assigned
    to a station (i.e., their `STATION` field is NULL).
    """

    login_id = request.session.get('user_id')
    if not login_id:
         return redirect(reverse('login'))

    # 2. Fetch the Officer Record
    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
    except ObjectDoesNotExist:
        # This is a data integrity issue: a login record exists, but the officer profile is gone.
        # Log them out completely to prevent a login loop.
        request.session.flush()
        return redirect(reverse('login'))
    except Exception as e:
         print(f"Error retrieving officer for home dashboard: {e}")
         return render(request, 'error_page.html', {'message': "An error occurred loading your profile."})


    # 3. Handle Station-Dependent Data Safely
    officer_station = officer.STATION  # This will be a station object or None

    # --- Initialize all variables with default "unassigned" values ---
    officer_station_id = None
    officer_station_name = "Unassigned"
    officer_station_latitude = None
    officer_station_longitude = None
    officer_cameras = []
    active_camera_count = 0
    recent_alerts_count = 0
    new_complaints_count = 0
    user_reports_new_count = 0

    # --- Only run these queries IF the officer is assigned to a station ---
    if officer_station is not None:
        officer_station_id = officer_station.id
        officer_station_name = officer_station.name
        officer_station_latitude = officer_station.latitude
        officer_station_longitude = officer_station.longitude
        
        # --- Calculate counts and get related data for the dashboard cards ---
        officer_cameras = camera.objects.filter(station=officer_station)
        active_camera_count = officer_cameras.count()

        now = timezone.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        recent_alerts_count = camera_alerts.objects.filter(
            CAMERA__station=officer_station,
            date__gte=twenty_four_hours_ago.date()
        ).count()

        new_complaints_count = complaints.objects.filter(
            STATION=officer_station, 
            reply__exact=""  # More explicit check for empty string
        ).count()

        user_reports_new_count = user_upload.objects.filter(
            station=officer_station
        ).exclude(
            status__in=['verified', 'inconclusive']
        ).count()

    # 4. Prepare Context for the Template
    # Get officer-specific data that doesn't depend on the station
    officer_image_url = officer.image.url if officer.image and hasattr(officer.image, 'url') else None

    context = {
        # Officer-specific details
        'officer_username': officer.username,
        'officer_first_name': officer.first_name,
        'officer_image_url': officer_image_url,

        # Station-specific details (will have default values if unassigned)
        'officer_station_id': officer_station_id,
        'officer_station_name': officer_station_name,
        'officer_latitude': officer_station_latitude,
        'officer_longitude': officer_station_longitude,
        
        # Dashboard counts (will be 0 if unassigned)
        'active_camera_count': active_camera_count,
        'recent_alerts_count': recent_alerts_count,
        'new_complaints_count': new_complaints_count,
        'user_reports_new_count': user_reports_new_count,

        # Other data
        'officer_cameras': officer_cameras,
        'web_launcher_url': WEB_LAUNCHER_URL,
    }

    # 5. Render the page
    return render(request, 'Forest Officer/Forest_Officer_Home.html', context)



class CustomSessionAuthentication(SessionAuthentication):
    """
    A custom session authentication class for DRF that primarily enables
    session cookie handling without relying on Django's default User model
    for `request.user` population for authentication decisions.
    Our permissions will explicitly use `request.session`.
    """
    # This class mainly ensures that the session cookie is processed.
    # We rely on our custom permission for actual authorization based on session content.
    pass

class IsOfficerAssignedToStation(permissions.BasePermission):
    """
    Custom permission to only allow officers assigned to a specific station
    to modify dangerous areas within that station, based on session data.
    Allows read-only access for any visitor (authenticated or not).
    """
    message = "You are not authorized to perform this action."

    def get_officer_from_session(self, request):
        """Helper to get the forest_officer instance from the session."""
        session = getattr(request, 'session', None) or getattr(getattr(request, '_request', None), 'session', None)
        if not session:
            return None

        login_id = session.get('user_id')
        user_type = session.get('user_type')

        if not login_id or user_type != 'officer':
            self.message = "You must be logged in as an officer to perform this action."
            return None

        try:
            # Check if the login_id actually corresponds to a forest_officer
            officer = forest_officer.objects.get(LOGIN__id=login_id)
            return officer
        except ObjectDoesNotExist:
            self.message = "Officer profile not found for your session. Please re-login."
            return None
        except Exception as e:
            self.message = f"An internal error occurred: {e}"
            return None

    def has_permission(self, request, view):
        # Allow read-only access (GET, HEAD, OPTIONS) for anyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # For write operations (POST, PUT, DELETE), user must be an authenticated officer.
        officer = self.get_officer_from_session(request)
        if not officer:
            return False # Deny if not an officer or session invalid

        # If it's a creation request (POST), check if the officer is authorized for the target station.
        if request.method == 'POST':
            station_id_from_request = request.data.get('station_id')
            if not station_id_from_request:
                self.message = "Station ID is required to create a dangerous area."
                return False
            try:
                # Ensure the officer's station matches the station ID from the request data
                return officer.STATION.id == int(station_id_from_request)
            except (ValueError, TypeError):
                self.message = "Invalid station ID format."
                return False
            except ObjectDoesNotExist:
                # This should ideally not happen if officer is valid and station_id is for an existing station
                self.message = "Assigned station not found for the requested station ID."
                return False

        return True # For PUT/DELETE, object-level permission will be checked next

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request (already handled by has_permission)
        if request.method in permissions.SAFE_METHODS:
            return True

        # For write operations (PUT, DELETE) on an existing object:
        # Check if the authenticated officer is assigned to the station of the dangerous area object being modified.
        officer = self.get_officer_from_session(request)
        if not officer:
            return False # Deny if not an officer or session invalid

        # Check if the officer's assigned station matches the dangerous area's station
        return officer.STATION == obj.station


@never_cache
def view_officer_profile(request):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        messages.warning(request, "You are not authorized to view this page.")
        if request.session.get('user_type') == 'admin':
            return redirect(reverse('admin_home')) # Replace 'admin_home'
        else:
            return redirect(reverse('login')) # Replace 'login'

    login_id = request.session.get('user_id')
    if not login_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect(reverse('login')) 

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found.")
        # Replace 'forest_officer_home' with the correct name for the officer's dashboard/home
        return redirect(reverse('forest_officer_home')) 

    context = {
        'officer': officer,
        'page_title': 'View Profile'
    }
    return render(request, 'Forest Officer/view_officer_profile.html', context)


@never_cache
def edit_officer_profile(request):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        messages.warning(request, "You are not authorized to perform this action.")
        return redirect(reverse('login'))

    login_id = request.session.get('user_id')
    if not login_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect(reverse('login'))

    try:
        officer_profile = forest_officer.objects.get(LOGIN_id=login_id)
        login_instance = officer_profile.LOGIN
    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found.")
        return redirect(reverse('forest_officer_home'))
    except Exception as e: # Catch general errors like LOGIN being None if DB allows
        messages.error(request, f"An error occurred loading profile: {e}")
        return redirect(reverse('forest_officer_home'))
    
    if login_instance is None: # Should ideally be prevented by DB constraints
            messages.error(request, "Critical error: Associated login account not found for officer.")
            return redirect(reverse('forest_officer_home'))


    if request.method == 'POST':
        username_updated_for_login_table = False
        form_has_errors = False

        first_name = request.POST.get('first_name', '').strip()
        if not first_name:
            messages.error(request, "First name cannot be empty.")
            form_has_errors = True
        else:
            officer_profile.first_name = first_name
            
        last_name = request.POST.get('last_name', '').strip()
        if not last_name:
            messages.error(request, "Last name cannot be empty.")
            form_has_errors = True
        else:
            officer_profile.last_name = last_name

        officer_profile.address = request.POST.get('address', officer_profile.address).strip() # Address can be empty
        
        phone_str = request.POST.get('phone', '').strip()
        if not phone_str:
            messages.error(request, "Phone number cannot be empty.")
            form_has_errors = True
        elif not phone_str.isdigit() or len(phone_str) != 10: # Strictly 10 digits
            messages.error(request, "Phone number must be exactly 10 digits.")
            form_has_errors = True
        elif forest_officer.objects.filter(phone=int(phone_str)).exclude(pk=officer_profile.pk).exists():
            messages.error(request, "This phone number is already registered.")
            form_has_errors = True
        else:
            officer_profile.phone = int(phone_str)

        email_val = request.POST.get('email', '').strip()
        email_regex_server = r'^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$' # Same as JS
        if not email_val:
            messages.error(request, "Email cannot be empty.")
            form_has_errors = True
        elif not re.fullmatch(email_regex_server, email_val): # Use re.fullmatch for server-side
            messages.error(request, "Invalid email format (e.g., user@example.com).")
            form_has_errors = True
        elif forest_officer.objects.filter(email__iexact=email_val).exclude(pk=officer_profile.pk).exists():
            messages.error(request, "This email address is already registered.")
            form_has_errors = True
        else:
            officer_profile.email = email_val


        dob_str = request.POST.get('dob', '')
        if dob_str:
            try:
                dob_date = datetime.strptime(dob_str, '%Y-%m-%d').date()
                today = date.today()
                # Ensure DOB is not in the future
                if dob_date > today:
                    messages.error(request, "Date of Birth cannot be in the future.")
                    form_has_errors = True
                else:
                    age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
                    if age < 18:
                        messages.error(request, "Officer must be at least 18 years old.")
                        form_has_errors = True
                    elif age > 60:
                        messages.error(request, "Officer cannot be older than 60 years.")
                        form_has_errors = True
                    else:
                        officer_profile.dob = dob_date
            except ValueError:
                messages.error(request, "Invalid date format for Date of Birth.")
                form_has_errors = True
        else:
            officer_profile.dob = None

        new_username = request.POST.get('username', '').strip()
        if not new_username:
            messages.error(request, "Username cannot be empty.")
            form_has_errors = True
        elif len(new_username) < 3:
             messages.error(request, "Username must be at least 3 characters long.")
             form_has_errors = True
        elif new_username != login_instance.username:
            if login_table.objects.filter(username__iexact=new_username).exclude(id=login_instance.id).exists():
                messages.error(request, f"The username '{new_username}' is already taken.")
                form_has_errors = True
            else:
                login_instance.username = new_username
                username_updated_for_login_table = True
        
        if 'image' in request.FILES:
            officer_profile.image = request.FILES['image']

        if not form_has_errors:
            try:
                officer_profile.save()
                if username_updated_for_login_table:
                    login_instance.save()
                messages.success(request, "Profile updated successfully!")
                return redirect(reverse('view_officer_profile'))
            except Exception as e:
                messages.error(request, f"An error occurred while saving: {e}")
        
        context = {
            'officer': officer_profile, 
            'page_title': 'Edit Profile'
        }
        return render(request, 'Forest Officer/edit_officer_profile.html', context)

    else: # GET request
        context = {
            'officer': officer_profile,
            'page_title': 'Edit Profile'
        }
        return render(request, 'Forest Officer/edit_officer_profile.html', context)

# Note: For the 'username' in login_instance to be saved, you might need to explicitly set a flag
# if new_username != officer_profile.username and not messages.get_messages(request):
#    login_instance._username_changed = True 
# else:
#    login_instance._username_changed = False
# This is a bit manual; Django Forms would handle this more cleanly.


@never_cache
def forest_officer_change_password(request):
    # Authentication and authorization check
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        if request.session.get('user_type') == 'admin':
            return redirect(reverse('admin_home'))
        else:
            return redirect(reverse('login'))

    login_id = request.session.get('user_id')
    if not login_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect(reverse('login'))

    try:
        login_entry = login_table.objects.get(id=login_id)
        # Get the actual username from the login_table
        officer_actual_username = login_entry.username
    except login_table.DoesNotExist:
        messages.error(request, "User account not found. Please log in again.")
        request.session.flush()
        return redirect(reverse('login'))

    # Get officer's first name for display
    officer_first_name = "Officer" # Default
    try:
        officer = forest_officer.objects.get(LOGIN=login_entry)
        officer_first_name = officer.first_name
    except forest_officer.DoesNotExist:
        # This case means login_entry exists but no corresponding forest_officer.
        # This shouldn't happen in a consistent DB, but good to be aware.
        messages.warning(request, "Officer profile details not found, but account exists.")


    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_new_password = request.POST.get('confirm_new_password')

        if not all([current_password, new_password, confirm_new_password]):
            messages.error(request, "All fields are required.")
        elif not check_password(current_password, login_entry.password) and login_entry.password != current_password:
            messages.error(request, "Incorrect current password.")
        elif new_password != confirm_new_password:
            messages.error(request, "New passwords do not match.")
        elif len(new_password) < 6:
            messages.error(request, "New password must be at least 6 characters long.")
        elif new_password == current_password:
            messages.error(request, "New password cannot be the same as the current password.")
        else:
            login_entry.password = make_password(new_password)
            login_entry.save()
            messages.success(request, "Password changed successfully!")
            return redirect(reverse('forest_officer_home'))

        context = {
            'officer_first_name': officer_first_name,
            'officer_actual_username': officer_actual_username, # Pass for the form
        }
        return render(request, 'Forest Officer/Change_Password.html', context)

    # For GET request
    context = {
        'officer_first_name': officer_first_name,
        'officer_actual_username': officer_actual_username, # Pass for the form
    }
    return render(request, 'Forest Officer/Change_Password.html', context)



from .spatial_utils import validate_geojson_geometry, is_polygon_within_station_buffer, check_point_in_dangerous_areas
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

class DangerousAreaViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows dangerous areas to be viewed or edited.
    Allows all users (including Android app) to view all polygons.
    Allows officers to create/edit/delete only polygons associated with their assigned station.
    """
    queryset = DangerousArea.objects.all().order_by('-created_at')
    serializer_class = DangerousAreaSerializer
    # Use your custom session authentication
    authentication_classes = [CustomSessionAuthentication, BasicAuthentication]
    # Use your custom permission for authorization
    permission_classes = [IsOfficerAssignedToStation]

    def get_queryset(self):
        """
        Allow all users to view all dangerous areas.
        The permission class handles editing/deleting restrictions.
        """
        return DangerousArea.objects.all().order_by('-created_at')


    def perform_create(self, serializer):
        """
        When creating a new dangerous area, associate it with the current officer
        and automatically assign the station based on the officer's assigned station.
        Validates that the drawn polygon lies within the 10km station buffer.
        """
        officer = self.permission_classes[0]().get_officer_from_session(self.request)
        if not officer:
            raise serializers.ValidationError("Officer not found or not authorized to create this area.")

        station = officer.STATION
        geojson = serializer.validated_data.get('geojson_data')
        if station and station.latitude and station.longitude:
            intersects, min_dist_km = is_polygon_within_station_buffer(
                geojson, station.latitude, station.longitude, buffer_km=10.0
            )
            if not intersects:
                raise serializers.ValidationError(
                    f"Polygon is outside your assigned station's 10km boundary zone (nearest point is {min_dist_km}km away)."
                )

        serializer.save(created_by_officer=officer, station=station)

    def perform_update(self, serializer):
        """
        Validates updated polygon boundary against station buffer.
        """
        officer = self.permission_classes[0]().get_officer_from_session(self.request)
        station = officer.STATION if officer and hasattr(officer, 'STATION') else serializer.instance.station
        geojson = serializer.validated_data.get('geojson_data', serializer.instance.geojson_data)
        if station and station.latitude and station.longitude:
            intersects, min_dist_km = is_polygon_within_station_buffer(
                geojson, station.latitude, station.longitude, buffer_km=10.0
            )
            if not intersects:
                raise serializers.ValidationError(
                    f"Polygon is outside station's 10km boundary zone (nearest point is {min_dist_km}km away)."
                )

        serializer.save()


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def check_dangerous_location(request):
    """
    API endpoint to check if a lat/lng location lies inside any dangerous area polygon.
    Accepts GET parameters `lat` & `lng` or POST JSON payload `{"latitude": ..., "longitude": ...}`.
    """
    lat, lng = None, None
    if request.method == 'POST':
        try:
            data = request.data if hasattr(request, 'data') else json.loads(request.body)
            lat = data.get('latitude') or data.get('lat')
            lng = data.get('longitude') or data.get('lng')
        except Exception:
            pass
    else:
        lat = request.GET.get('lat') or request.GET.get('latitude')
        lng = request.GET.get('lng') or request.GET.get('longitude')

    if lat is None or lng is None:
        return Response({'error': 'Missing latitude or longitude parameters.'}, status=400)

    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid latitude or longitude numeric values.'}, status=400)

    areas_qs = DangerousArea.objects.all()
    stations_qs = forest_station.objects.all()
    result = check_point_in_dangerous_areas(lat, lng, areas_qs, station_queryset=stations_qs)
    result['latitude'] = lat
    result['longitude'] = lng
    return Response(result)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_map_cameras_api(request):
    """
    API endpoint returning cameras for map overlay pins.
    Filters cameras by officer's assigned station if logged in or if station_id is supplied.
    """
    cameras_qs = camera.objects.all().select_related('station')

    station_id = request.GET.get('station_id')
    if not station_id:
        permission_helper = IsOfficerAssignedToStation()
        officer = permission_helper.get_officer_from_session(request)
        if officer and officer.STATION:
            station_id = officer.STATION.id

    if station_id:
        try:
            cameras_qs = cameras_qs.filter(station_id=int(station_id))
        except (ValueError, TypeError):
            pass

    serializer = CameraMapSerializer(cameras_qs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_map_animal_alerts_api(request):
    """
    API endpoint returning recent camera animal alerts for live map pins.
    Filters alerts by officer's assigned station if logged in or if station_id is supplied.
    """
    alerts_qs = camera_alerts.objects.all().select_related('CAMERA', 'ANIMAL', 'CAMERA__station').order_by('-created_at')

    station_id = request.GET.get('station_id')
    if not station_id:
        permission_helper = IsOfficerAssignedToStation()
        officer = permission_helper.get_officer_from_session(request)
        if officer and officer.STATION:
            station_id = officer.STATION.id

    if station_id:
        try:
            alerts_qs = alerts_qs.filter(CAMERA__station_id=int(station_id))
        except (ValueError, TypeError):
            pass

    alerts_qs = alerts_qs[:50]
    serializer = CameraAlertMapSerializer(alerts_qs, many=True, context={'request': request})
    return Response(serializer.data)


# --- NEW: View for Map Management Page ---
@never_cache
@ensure_csrf_cookie # Ensures CSRF cookie is set for API calls from this page
def manage_dangerous_area_map(request):
    # This view performs similar authentication checks as forest_officer_home
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        if request.session.get('user_type') == 'admin':
             return redirect(reverse('admin_home'))
        else:
            return redirect(reverse('login'))

    login_id = request.session.get('user_id')
    if not login_id:
         return redirect(reverse('login'))

    officer_station_id = None
    officer_station_name = None
    officer_station_latitude = None
    officer_station_longitude = None
    officer_username = None

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station_id = officer.STATION.id
        officer_station_name = officer.STATION.name
        officer_station_latitude = officer.STATION.latitude
        officer_station_longitude = officer.STATION.longitude
        officer_username = officer.username
    except ObjectDoesNotExist:
        # If officer profile not found for the session, redirect to login
        return redirect(reverse('login'))
    except Exception as e:
        print(f"Error retrieving officer/station for map management: {e}")
        return HttpResponse("An error occurred loading map data.", status=500)

    context = {
        'officer_station_id': officer_station_id,
        'officer_station_name': officer_station_name,
        'officer_latitude': officer_station_latitude,
        'officer_longitude': officer_station_longitude,
        'officer_username': officer_username,
    }

    return render(request, 'Forest Officer/Forest_Officer_Map_Management.html', context)

# NEW: API ViewSet for Forest Stations (read-only)
# Define a custom pagination class that returns no pagination
class NoPagination(PageNumberPagination):
    page_size = None # Set page_size to None to disable pagination
    page_size_query_param = None
    max_page_size = None
    
class ForestStationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows forest stations to be viewed.
    This is for public read-only access to station coordinates for map display.
    """
    queryset = forest_station.objects.all().order_by('name') 
    serializer_class = ForestStationSerializer
    # permission_classes = [permissions.AllowAny] # Allow anyone to read station data
    # NEW: Assign the custom NoPagination class to disable pagination
    pagination_class = NoPagination
    # No custom get_queryset needed here, as it's a public list of stations

# NEW: Publicly accessible map view for users (Android App)
# This view will display the map with dangerous areas and station boundaries
# It does NOT require login.
def public_dangerous_area_map(request):
    """
    Renders a public HTML page with the map showing dangerous areas and forest station boundaries.
    Accessible to anyone, without requiring a login.
    """
    # No officer-specific data or CSRF token is needed for a read-only map.
    # The map will fetch dangerous areas and station data via API calls.
    context = {} # Empty context as data will be fetched client-side.
    return render(request, 'Public_Map/Public_Dangerous_Area_Map.html', context)


#Entire views.py code block for Adding Forest Division-----------------(working):

def admin_add_forest_divition(request):
    return  render(request, 'Admin/Add_Forest_Divition.html')

@require_GET
def admin_check_field_exists(request):
    model_name_str = request.GET.get('model_name', None)
    field_name_str = request.GET.get('field_name', None) # This will be like 'station_name', 'station_place'
    field_value = request.GET.get('field_value', None)
    exclude_id_str = request.GET.get('exclude_id', None) # For edit scenarios

    data = {'exists': False, 'error': None}

    if not model_name_str or not field_name_str or not field_value:
        data['error'] = 'Model, field name, or value missing for check.'
        return JsonResponse(data, status=400)

    model_to_check = None
    actual_db_field_name = None # The real field name in the Django model

    if model_name_str == 'forest_division':
        model_to_check = forest_division
        if field_name_str == 'name': # Name of the division
            actual_db_field_name = 'name'
        elif field_name_str == 'place': # Place of the division
            actual_db_field_name = 'place'
        else:
            data['error'] = f"Invalid field '{field_name_str}' for model '{model_name_str}'."
            return JsonResponse(data, status=400)

    elif model_name_str == 'forest_station':
        model_to_check = forest_station
        if field_name_str == 'station_name': # Corresponds to 'name' in forest_station model
            actual_db_field_name = 'name'
        elif field_name_str == 'station_place': # Corresponds to 'place' in forest_station model
            actual_db_field_name = 'place'
        elif field_name_str == 'station_phone': # Corresponds to 'phone' in forest_station model
            actual_db_field_name = 'phone'
        else:
            data['error'] = f"Invalid field '{field_name_str}' for model '{model_name_str}'."
            return JsonResponse(data, status=400)
    else:
        data['error'] = f"Unsupported model '{model_name_str}' for existence check."
        return JsonResponse(data, status=400)

    # Basic length/format pre-checks before DB query (can be more specific)
    if actual_db_field_name == 'name' and len(field_value) < 3: # Station Name or Division Name
        data['message'] = 'Name too short for validation.'
        return JsonResponse(data)
    if actual_db_field_name == 'place' and model_name_str == 'forest_station' and (len(field_value) < 2 or re.search(r'\d', field_value)):
        data['message'] = 'Place (Station) format invalid for validation.'
        return JsonResponse(data)
    if actual_db_field_name == 'phone' and not re.match(r"^[6-9]\d{9}$", field_value):
        data['message'] = 'Phone format invalid for validation.'
        return JsonResponse(data)


    try:
        # For phone, it's stored as BigIntegerField, so try to cast if needed, though comparison as string might be okay with iexact for some DBs
        # For exact match on numbers, direct equality is better if type is consistent.
        if actual_db_field_name == 'phone':
            query_filter = {actual_db_field_name: field_value} # Direct match for phone
        else:
            query_filter = {f"{actual_db_field_name}__iexact": field_value} # Case-insensitive for text

        query = model_to_check.objects.filter(**query_filter)

        if exclude_id_str:
            try:
                exclude_id = int(exclude_id_str)
                query = query.exclude(id=exclude_id)
            except ValueError:
                data['error'] = 'Invalid exclude_id format.'
                return JsonResponse(data, status=400)
        
        data['exists'] = query.exists()

    except Exception as e:
        print(f"Error in admin_check_field_exists: {e}") # Log error
        data['error'] = 'Server error during existence check.'
        return JsonResponse(data, status=500)
        
    return JsonResponse(data)

@require_POST
def admin_add_forest_divition_post(request):
    name_from_post = request.POST.get('name', '').strip()
    place_from_post = request.POST.get('place', '').strip()

    # ... (name validation logic as before) ...
    division_name_regex_str = r"^\s*([\w\s'-]+?)\s+(?:[Dd][Ii][Vv][Ii][Ss][Ii][Oo][Nn])(\s+[\w\s'-]*)?\s*$"
    standardized_name = name_from_post
    match_name = re.match(division_name_regex_str, name_from_post, re.IGNORECASE) # Renamed match to match_name
    errors = {}
    if not name_from_post: errors['name'] = 'Division Name cannot be empty.'
    elif len(name_from_post) < 3: errors['name'] = 'Division Name must be at least 3 characters long.'
    elif not match_name: errors['name'] = 'Name must be in the format "Text Division OptionalText".'
    else:
        part1 = match_name.group(1).strip()
        part2_optional = match_name.group(2).strip() if match_name.group(2) else ""
        standardized_name = f"{part1} Division {part2_optional}".strip() if part2_optional else f"{part1} Division".strip()
        if forest_division.objects.filter(name__iexact=standardized_name).exists():
            errors['name'] = f'Forest Division "{standardized_name}" already exists.'


    # Place validation
    if not place_from_post:
        errors['place'] = 'Place cannot be empty.'
    elif len(place_from_post) < 2:
        errors['place'] = 'Place must be at least 2 characters.'
    elif re.search(r'\d', place_from_post): # Check if place contains any digit
        errors['place'] = 'Place name cannot contain numbers.'
    # Informational check for existence (does not block) can be done here if desired,
    # but client-side handles the info message. Server mainly cares about blocking errors.

    if errors:
        for field, error_msg in errors.items(): messages.error(request, error_msg)
        return render(request, 'Admin/Add_Forest_Divition.html', {'form_data': request.POST, 'errors': errors})

    obj = forest_division(name=standardized_name, place=place_from_post)
    obj.save()
    messages.success(request, f'Forest Division "{standardized_name}" added successfully!')
    return redirect('admin_view_forest_divition')



@require_GET # Ensure admin_check_division_name is GET only
def admin_check_division_name(request):
    name_to_check = request.GET.get('name', None)
    exclude_id_str = request.GET.get('exclude_id', None) # Get as string
    data = {'exists': False}

    if name_to_check and len(name_to_check) >= 3:
        query = forest_division.objects.filter(name__iexact=name_to_check)
        if exclude_id_str:
            try:
                # Ensure exclude_id is a valid integer before using in query
                exclude_id = int(exclude_id_str)
                query = query.exclude(id=exclude_id)
            except ValueError:
                # Handle cases where exclude_id is not a valid integer,
                # though JS should send it correctly.
                # For safety, you might log this or decide how to handle.
                # If it's invalid, we proceed without excluding, which might give a false positive
                # if the invalid ID somehow matched an existing one.
                # Or, consider returning an error if exclude_id is present but invalid.
                pass # Or data['error'] = 'Invalid exclude_id format'
        data['exists'] = query.exists()
    # else if name_to_check: (but too short)
        # data['error'] = 'Name too short for validation'
    return JsonResponse(data)

@require_GET
def admin_check_division_place(request):
    place_to_check = request.GET.get('place', None)
    exclude_id_str = request.GET.get('exclude_id', None) # For edit form
    data = {'exists': False, 'message': ''}

    if not place_to_check:
        data['message'] = 'Place cannot be empty for check.'
        return JsonResponse(data, status=400) # Bad request

    if len(place_to_check) < 2: # Consistent with client-side min length
        data['message'] = 'Place too short for validation.'
        # data['exists'] could remain false, or you could set it true to prevent submission
        return JsonResponse(data)


    query = forest_division.objects.filter(place__iexact=place_to_check)
    
    if exclude_id_str:
        try:
            exclude_id = int(exclude_id_str)
            query = query.exclude(id=exclude_id)
        except ValueError:
            data['message'] = 'Invalid ID format for exclusion.'
            return JsonResponse(data, status=400) # Bad request
            
    if query.exists():
        data['exists'] = True
        data['message'] = f"The place '{place_to_check}' is already in use."
    else:
        data['exists'] = False
        data['message'] = f"The place '{place_to_check}' is available."
        
    return JsonResponse(data)


def admin_view_forest_divition(request):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        # Optionally, redirect officer to their home page if logged in but not admin
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # If checks pass, proceed with the view logic


    divisions = forest_division.objects.all()
#search box code below:
    if request.method == 'POST':
        search_term = request.POST.get('textfield', '').strip()
        if search_term:
            divisions = forest_division.objects.filter(
                Q(name__icontains=search_term) |
                Q(place__icontains=search_term)
            )

    context = {'divisions': divisions}
    return render(request, 'Admin/View_Forest_Divition.html', context)
#search box code^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

def admin_edit_forest_divition(request, id):
    division = get_object_or_404(forest_division, id=id)
    original_name_for_check = division.name
    original_place_for_check = division.place

    if request.method == 'POST':
        name_from_post = request.POST.get('name', '').strip()
        place_from_post = request.POST.get('place', '').strip()

        # ... (name validation logic as before) ...
        division_name_regex_str = r"^\s*([\w\s'-]+?)\s+(?:[Dd][Ii][Vv][Ii][Ss][Ii][Oo][Nn])(\s+[\w\s'-]*)?\s*$"
        standardized_name = name_from_post
        match_name = re.match(division_name_regex_str, name_from_post, re.IGNORECASE) # Renamed match to match_name
        errors = {}
        if not name_from_post: errors['name'] = 'Division Name cannot be empty.'
        # ... (rest of name validation) ...
        elif not match_name: errors['name'] = 'Name must be in the format "Text Division OptionalText".'
        else:
            part1 = match_name.group(1).strip()
            part2_optional = match_name.group(2).strip() if match_name.group(2) else ""
            standardized_name = f"{part1} Division {part2_optional}".strip() if part2_optional else f"{part1} Division".strip()
            if standardized_name.lower() != original_name_for_check.lower():
                if forest_division.objects.filter(name__iexact=standardized_name).exclude(id=division.id).exists():
                    errors['name'] = f'Another division with name "{standardized_name}" already exists.'
        
        # Place validation
        if not place_from_post:
            errors['place'] = 'Place cannot be empty.'
        elif len(place_from_post) < 2:
            errors['place'] = 'Place must be at least 2 characters.'
        elif re.search(r'\d', place_from_post): # Check if place contains any digit
            errors['place'] = 'Place name cannot contain numbers.'

        if errors:
            for field, error_msg in errors.items(): messages.error(request, error_msg)
            current_form_values = division
            current_form_values.name = name_from_post
            current_form_values.place = place_from_post
            return render(request, 'Admin/Edit_Forest_Divition.html', {'division': current_form_values, 'errors': errors})

        division.name = standardized_name
        division.place = place_from_post
        division.save()
        messages.success(request, f'Forest Division "{standardized_name}" updated successfully!')
        return redirect('admin_view_forest_divition')

    return render(request, 'Admin/Edit_Forest_Divition.html', {'division': division})



def admin_delete_forest_divition(request, id):
    # Fetch the division object we want to potentially delete
    division = get_object_or_404(forest_division, id=id)
    
    # Fetch all stations that are linked to this division
    associated_stations = forest_station.objects.filter(DIVISION=division)
    
    # If the form on the confirmation page has been submitted
    if request.method == 'POST':
        # This is where the actual deletion happens
        division_name = division.name # Save the name for the message
        division.delete()
        
        # Use Django's messages framework for a cleaner user notification
        messages.success(request, f"The division '{division_name}' and all its stations have been successfully deleted.")
        
        # Redirect back to the list of divisions
        return redirect('admin_view_forest_divition')

    # If it's a GET request, just display the confirmation page
    context = {
        'division': division,
        'associated_stations': associated_stations
    }
    
    # Make sure the path to your template is correct
    return render(request, 'Admin/Confirm_Delete_Division.html', context)


def admin_add_forest_station(request):
    """
    Renders the add forest station form, passing the list of forest divisions.
    """
    divisions = forest_division.objects.all() # Fetch all divisions
    context = {
        'divisions': divisions # Pass divisions to the template context
    }
    return render(request, 'Admin/Add_Forest_Station.html', context)



@require_POST # Ensures this view only accepts POST requests
def admin_add_forest_station_post(request):
    """
    Handles the POST request to add a new forest station,
    including comprehensive server-side validation.
    """
    # Retrieve all data from POST
    station_name_from_post = request.POST.get('name', '').strip()
    station_place_from_post = request.POST.get('place', '').strip()
    division_id_str = request.POST.get('division', '').strip()
    phone_str = request.POST.get('phone', '').strip()
    latitude_str = request.POST.get('latitude', '').strip()
    longitude_str = request.POST.get('longitude', '').strip()

    errors = {} # Dictionary to store validation errors

    # 1. Validate Station Name
    if not station_name_from_post:
        errors['name'] = "Station Name is required."
    elif len(station_name_from_post) < 3:
        errors['name'] = "Station Name must be at least 3 characters long."
    elif forest_station.objects.filter(name__iexact=station_name_from_post).exists():
        errors['name'] = "A Forest Station with this name already exists."

    # 2. Validate Station Place
    if not station_place_from_post:
        errors['place'] = "Place is required for the station."
    elif len(station_place_from_post) < 2:
        errors['place'] = "Place must be at least 2 characters long."
    elif re.search(r'\d', station_place_from_post): # Check for numbers
        errors['place'] = "Place name cannot contain numbers."
    # elif forest_station.objects.filter(place__iexact=station_place_from_post).exists():
    #     errors['place'] = "This Place is already assigned to another Forest Station."

    # 3. Validate Division
    selected_division_obj = None
    if not division_id_str:
        errors['division'] = "A Division must be selected."
    else:
        try:
            division_id = int(division_id_str)
            selected_division_obj = forest_division.objects.get(pk=division_id)
        except ValueError:
            errors['division'] = "Invalid Division ID format."
        except forest_division.DoesNotExist:
            errors['division'] = "The selected Division does not exist."

    # 4. Validate Phone Number
    phone_num_int = None
    if not phone_str:
        errors['phone'] = "Phone number is required."
    elif not re.match(r"^[6-9]\d{9}$", phone_str):
        errors['phone'] = "Phone number must be a 10-digit number starting with 6, 7, 8, or 9."
    else:
        # Check for uniqueness only if format is valid
        if forest_station.objects.filter(phone=phone_str).exists(): # Phone is stored as BigInt, direct match is fine
            errors['phone'] = "This Phone number is already registered to a station."
        else:
            try:
                phone_num_int = int(phone_str) # Convert to int for saving
            except ValueError: # Should not happen if regex matches, but as a safeguard
                errors['phone'] = "Phone number contains invalid characters."


    # 5. Validate Latitude
    latitude_float = None
    if not latitude_str: # Latitude is required (set by map)
        errors['latitude'] = "Latitude is required. Please pick a location on the map."
    else:
        try:
            latitude_float = float(latitude_str)
            if not (-90 <= latitude_float <= 90):
                errors['latitude'] = "Latitude must be between -90 and 90."
        except ValueError:
            errors['latitude'] = "Latitude must be a valid number."

    # 6. Validate Longitude
    longitude_float = None
    if not longitude_str: # Longitude is required
        errors['longitude'] = "Longitude is required. Please pick a location on the map."
    else:
        try:
            longitude_float = float(longitude_str)
            if not (-180 <= longitude_float <= 180):
                errors['longitude'] = "Longitude must be between -180 and 180."
        except ValueError:
            errors['longitude'] = "Longitude must be a valid number."

    # If there are any errors, re-render the form with error messages and old data
    if errors:
        for field, error_message in errors.items():
            messages.error(request, f"{field.replace('_', ' ').capitalize()}: {error_message}")
        
        all_divisions = forest_division.objects.all()
        context = {
            'divisions': all_divisions,
            'form_data': request.POST, # To repopulate the form with user's previous input
            'errors_dict': errors # Optional: if template handles showing errors next to fields directly
        }
        return render(request, 'Admin/Add_Forest_Station.html', context)

    # If all validations pass, create and save the new Forest Station
    try:
        new_station = forest_station(
            name=station_name_from_post,
            place=station_place_from_post,
            DIVISION=selected_division_obj,
            phone=phone_num_int, # Use the validated integer phone number
            latitude=latitude_float,
            longitude=longitude_float
        )
        new_station.save()
        messages.success(request, f"Forest Station '{station_name_from_post}' added successfully!")
        return redirect('admin_view_forest_station') # Redirect to a view that lists stations

    except Exception as e:
        # Log the exception e in a real application
        print(f"Unexpected error saving forest station: {e}")
        messages.error(request, f"An unexpected error occurred while saving the station: {e}")
        # It's generally better to redirect back to the form on unexpected errors too
        all_divisions = forest_division.objects.all()
        context = {
            'divisions': all_divisions,
            'form_data': request.POST,
        }
        return render(request, 'Admin/Add_Forest_Station.html', context)

def admin_view_forest_station(request):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        # Optionally, redirect officer to their home page if logged in but not admin
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # If checks pass, proceed with the view logic







    """
    Views all forest stations, supporting search by name.
    """
    # Get all stations initially
    stations = forest_station.objects.all()
    search_term = '' # Initialize search_term

    if request.method == 'POST':
        # Handle search submission
        search_term = request.POST.get('textfield', '').strip() # Get the search text, remove leading/trailing spaces
        if search_term:
            # Filter stations by name (case-insensitive contains)
            stations = stations.filter(
                Q(name__icontains=search_term) |
                Q(place__icontains=search_term) |
                Q(DIVISION__name__icontains=search_term)   # Search in the related Division's name
            )
    # Create the context dictionary
    context = {
        'stations': stations,
        'search_term': search_term # Pass the search term back to the template (optional, but good practice)
    }

    # Pass the context dictionary to the render function
    return render(request, 'Admin/View_Forest_Station.html', context)


def admin_edit_forest_station(request, id):
    station = get_object_or_404(forest_station, pk=id)
    all_divisions = forest_division.objects.all()

    print(f"\n--- Debugging admin_edit_forest_station for Station ID: {id} ---")
    print(f"Station's current DIVISION ID: {station.DIVISION_id}")
    print(f"Station's current DIVISION Name: {station.DIVISION.name if station.DIVISION else 'N/A'}")

    if request.method == 'POST':
        print("--- POST Request ---")
        # ... (your existing POST logic for retrieving data and validation) ...
        station_name_from_post = request.POST.get('name', '').strip()
        station_place_from_post = request.POST.get('place', '').strip()
        division_id_str = request.POST.get('division', '').strip() # This is key
        phone_str = request.POST.get('phone', '').strip()
        latitude_str = request.POST.get('latitude', '').strip()
        longitude_str = request.POST.get('longitude', '').strip()

        print(f"POSTED division_id_str: '{division_id_str}' (Type: {type(division_id_str)})")
        errors = {}

        # ... (all your validation logic for name, place, phone, lat, lon) ...
        # Example for division part of validation:
        selected_division_obj = None
        if not division_id_str:
            errors['division'] = "A Division must be selected."
        else:
            try:
                division_id_int_from_post = int(division_id_str) # Convert to int
                selected_division_obj = forest_division.objects.get(pk=division_id_int_from_post)
                print(f"POST: Successfully fetched selected_division_obj with ID: {selected_division_obj.id}")
            except ValueError:
                errors['division'] = "Invalid Division ID format from POST."
                print(f"POST Error: ValueError converting division_id_str '{division_id_str}' to int.")
            except forest_division.DoesNotExist:
                errors['division'] = "The selected Division from POST does not exist."
                print(f"POST Error: forest_division with ID '{division_id_str}' does not exist.")


        if errors:
            print(f"POST: Validation Errors Found: {errors}")
            for field, error_message in errors.items():
                messages.error(request, f"{field.replace('_', ' ').capitalize()}: {error_message}")
            
            # CRITICAL: Ensure request.POST is passed as form_data
            form_data_for_template = request.POST 
            print(f"POST Error: Repopulating template with form_data: {form_data_for_template}")
            context = {
                'station': station, 
                'divisions': all_divisions,
                'form_data': form_data_for_template, 
                'errors_dict': errors
            }
            return render(request, 'Admin/Edit_Forest_Station.html', context)

        # ... (If NO errors, update and save logic) ...
        try:
            station.name = station_name_from_post
            station.place = station_place_from_post
            if selected_division_obj: # Make sure it was successfully fetched
                 station.DIVISION = selected_division_obj
            # ... rest of assignments ...
            station.phone = int(phone_str) # Assuming phone_num_int was validated
            station.latitude = float(latitude_str) if latitude_str else None
            station.longitude = float(longitude_str) if longitude_str else None

            station.save()
            messages.success(request, f"Forest Station '{station.name}' updated successfully!")
            return redirect('admin_view_forest_station') # Replace with your actual view name

        except Exception as e:
            print(f"POST Error: Unexpected error during save: {e}")
            # ... (error handling for save) ...
            messages.error(request, f"An unexpected error occurred: {e}")
            context = {
                'station': station,
                'divisions': all_divisions,
                'form_data': request.POST, 
            }
            return render(request, 'Admin/Edit_Forest_Station.html', context)

    else: # GET request
        print("--- GET Request ---")
        form_data_for_template = {
            'name': station.name,
            'place': station.place,
            'division': str(station.DIVISION_id), # Ensure it's a string for consistent comparison in template
            'phone': str(station.phone),
            'latitude': str(station.latitude) if station.latitude is not None else '',
            'longitude': str(station.longitude) if station.longitude is not None else '',
        }
        print(f"GET: Preparing form_data for template: {form_data_for_template}")
        context = {
            'station': station,
            'divisions': all_divisions,
            'form_data': form_data_for_template 
        }
        return render(request, 'Admin/Edit_Forest_Station.html', context)
    

def admin_delete_forest_station(request, id):
    # Fetch the station object we want to potentially delete
    station = get_object_or_404(forest_station, pk=id)
    
    # Fetch all officers that are linked to this station
    # The related name is 'forest_officer_set' by default. You can also query it directly.
    # assigned_officers = station.forest_officer_set.all()
    assigned_officers = forest_officer.objects.filter(STATION=station)

    # If the form on the confirmation page has been submitted (POST request)
    if request.method == 'POST':
        station_name = station.name  # Save name for the message
        
        # Because your model has on_delete=models.SET_NULL, this will
        # set the STATION field on the associated officer to NULL.
        station.delete()
        
        # Use Django's messages framework for a clean notification
        messages.success(request, f"The station '{station_name}' has been successfully deleted. Any assigned officers are now unassigned.")
        
        # Redirect back to the list of stations
        return redirect('admin_view_forest_station')

    # If it's a GET request, just display the confirmation page
    context = {
        'station': station,
        'assigned_officers': assigned_officers
    }
    
    # Render the confirmation template
    return render(request, 'Admin/Confirm_Delete_Station.html', context)    





# Entire views.py code block for Adding Forest Officer---------------(working partially)--:
def admin_add_forest_officer(request):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        # Optionally, redirect officer to their home page if logged in but not admin
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # If checks pass, proceed with the view logic






    stations = forest_station.objects.all() # Fetch all divisions
    stations_with_officers_ids = forest_officer.objects.values_list('STATION_id', flat=True).distinct()

    context = {
        'stations': stations, # Pass divisions to the template context
        'stations_with_officers_ids_js': list(stations_with_officers_ids) # Pass as a list for JSON

    }
    return  render(request, 'Admin/Add_Forest_Officer.html', context)

# NEW: View to check if username exists (for AJAX)
def check_username_exists(request):
    username = request.GET.get('username', None)
    login_id_to_exclude = request.GET.get('login_id', None) # Get login_id to exclude

    query = login_table.objects.filter(username__iexact=username)
    if login_id_to_exclude:
        try:
            # Exclude the current login entry being edited
            query = query.exclude(pk=int(login_id_to_exclude))
        except ValueError:
            pass # Handle if login_id_to_exclude is not a valid int

    data = {
        'is_taken': query.exists()
    }
    return JsonResponse(data)


def check_email_exists(request):
    email = request.GET.get('email', None)
    officer_id = request.GET.get('officer_id', None) # NEW: Get officer_id

    query = forest_officer.objects.filter(email__iexact=email)
    if officer_id:
        try:
            # Exclude the current officer being edited
            query = query.exclude(pk=int(officer_id))
        except ValueError:
            pass # Handle if officer_id is not a valid int

    data = {
        'is_taken': query.exists()
    }
    return JsonResponse(data)

def check_phone_exists(request):
    phone_str = request.GET.get('phone', None)
    officer_id = request.GET.get('officer_id', None) # NEW: Get officer_id
    is_taken = False

    if phone_str:
        try:
            phone_int = int(phone_str)
            query = forest_officer.objects.filter(phone=phone_int)
            if officer_id:
                try:
                    # Exclude the current officer being edited
                    query = query.exclude(pk=int(officer_id))
                except ValueError:
                    pass
            is_taken = query.exists()
        except ValueError:
            pass
    data = {
        'is_taken': is_taken
    }
    return JsonResponse(data)


#ADD FOREST OFFICER****************************
def admin_add_forest_officer_post(request):
    if request.method == 'POST':
        first_name = request.POST.get('textfield3')
        last_name = request.POST.get('textfield')
        dob = request.POST.get('simpleDate')
        address = request.POST.get('textarea')
        station_id_str = request.POST.get('select')
        phone_number_str = request.POST.get('textfield42')
        email = request.POST.get('textfield4')
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password or len(str(password)) < 6:
            return HttpResponse("<script> alert('Username and Password (min 6 characters) are required.'); window.history.back(); </script>")

        # Server-side uniqueness checks for username
        if login_table.objects.filter(username__iexact=username).exists() or RegularUserLogin.objects.filter(username__iexact=username).exists():
            return HttpResponse("<script> alert('Username already exists. Please choose a different one.'); window.history.back(); </script>")

        # Convert station_id to integer (crucial for ForeignKey lookup)
        try:
            station_id = int(station_id_str) if station_id_str else None
        except ValueError:
            return HttpResponse("<script> alert('Invalid station ID format.'); window.history.back(); </script>")

        # --- Server-Side Validation: Station Already Has Officer ---
        if station_id:
            if forest_officer.objects.filter(STATION_id=station_id).exists():
                return HttpResponse("<script> alert('This station already has an officer assigned. Please choose another station.'); window.history.back(); </script>")
        else:
            return HttpResponse("<script> alert('Please select a station.'); window.history.back(); </script>")

        # --- Server-side validation for Phone Number & Uniqueness ---
        if not phone_number_str or not phone_number_str.isdigit():
            return HttpResponse("<script> alert('Invalid phone number format. Please enter only digits.'); window.history.back(); </script>")
        phone_number = int(phone_number_str)

        if forest_officer.objects.filter(phone=phone_number).exists():
            return HttpResponse("<script> alert('This phone number is already registered to another officer.'); window.history.back(); </script>")

        # --- Server-side validation for Email Uniqueness ---
        if email and forest_officer.objects.filter(email__iexact=email).exists():
            return HttpResponse("<script> alert('This email address is already registered to another officer.'); window.history.back(); </script>")

        try:
            selected_station = forest_station.objects.get(pk=station_id)
        except forest_station.DoesNotExist:
            return HttpResponse("<script> alert('Error: Selected Forest Station does not exist.'); window.history.back(); </script>")

        # Use transaction.atomic for safe DB execution
        try:
            with transaction.atomic():
                # 1. Create login entry with HASHED password
                login_obj = login_table(
                    username=username,
                    password=make_password(password),
                    type='officer'
                )
                login_obj.save()

                # 2. Upload image file if present
                image_file = request.FILES.get('file')
                file_path = None
                if image_file:
                    fs = FileSystemStorage()
                    file_path = fs.save(image_file.name, image_file)

                # 3. Create forest_officer object
                obj = forest_officer(
                    first_name=first_name,
                    last_name=last_name,
                    dob=dob if dob else None,
                    address=address,
                    STATION=selected_station,
                    phone=phone_number,
                    email=email,
                    username=username,
                    password='',
                    LOGIN=login_obj
                )
                if file_path:
                    obj.image.name = file_path
                obj.save()

            return HttpResponse('''<script> alert('Forest Officer Added Successfully'); window.location='/admin_view_forest_officer'</script>''')
        except Exception as e:
            return HttpResponse(f"<script> alert('Error creating forest officer: {e}'); window.history.back(); </script>")
    else:
        return HttpResponse("<script> alert('Invalid request method.'); window.location='/admin_add_forest_officer'; </script>")



def admin_view_forest_officer(request):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        # Optionally, redirect officer to their home page if logged in but not admin
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # If checks pass, proceed with the view logic






    """
    Views all forest officers, supporting search by first name, last name, email, phone, station name, or station place.
    """
    # Get all officers initially with select_related for LOGIN and STATION
    officers = forest_officer.objects.select_related('LOGIN', 'STATION').all()
    search_term = '' # Initialize search_term

    if request.method == 'POST':
        # Handle search submission
        search_term = request.POST.get('textfield', '').strip() # Get the search text, remove leading/trailing spaces
        if search_term:
            # Filter officers by multiple fields (case-insensitive contains)
            # Using Q objects to combine conditions with OR
            filters = Q(first_name__icontains=search_term) | \
                      Q(last_name__icontains=search_term) | \
                      Q(email__icontains=search_term) | \
                      Q(STATION__name__icontains=search_term) | \
                      Q(STATION__place__icontains=search_term) # Search in the related Station's name and place

            # Handle phone number search: try converting search_term to int
            try:
                search_phone = int(search_term)
                filters |= Q(phone=search_phone) # Add exact match for phone number if it's a number
            except ValueError:
                # If search_term is not a number, don't add phone filter
                pass

            officers = officers.filter(filters)


    # Create the context dictionary
    context = {
        'officers': officers,
        'search_term': search_term # Pass the search term back to the template (optional)
    }

    # Pass the context dictionary to the render function
    return render(request, 'Admin/View_Forest_Officer.html', context)


def admin_edit_forest_officer(request, id):
    """
    Handles displaying the edit form and processing updates for a forest officer.
    'id' is the primary key of the forest_officer instance to be edited.
    """
    # Use select_related to efficiently fetch related LOGIN and STATION objects
    # This avoids N+1 query problems when accessing officer.LOGIN or officer.STATION
    officer = get_object_or_404(forest_officer.objects.select_related('LOGIN', 'STATION'), pk=id)
    
    # Get all stations for the dropdown in the form
    stations = forest_station.objects.all() 

    # For client-side validation: Get IDs of stations already assigned to OTHER officers.
    # This helps the JavaScript prevent assigning the current officer to a station
    # that another officer already occupies.
    stations_with_other_officers_ids = list(
        forest_officer.objects.exclude(pk=id)  # Exclude the current officer being edited
                          .filter(STATION__isnull=False) # Only consider officers who have a station
                          .values_list('STATION_id', flat=True) # Get only the station IDs
                          .distinct() # Ensure unique station IDs
    )

    if request.method == 'POST':
        # --- Retrieve original values for comparison (important for uniqueness checks if values change) ---
        original_username = officer.LOGIN.username
        original_email = officer.email
        original_phone = officer.phone
        original_station_id = officer.STATION.id if officer.STATION else None

        # --- Get data from the POST request ---
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        dob_str = request.POST.get('dob') # Date of Birth string
        address = request.POST.get('address', '').strip()
        station_id_str = request.POST.get('station') # Station ID string
        phone_number_str = request.POST.get('phone', '').strip()
        new_email = request.POST.get('email', '').strip().lower() # Normalize email to lowercase
        
        new_username = request.POST.get('username', '').strip()
        password_new = request.POST.get('password_new') # New password (if provided)
        password_confirm = request.POST.get('password_confirm') # Confirm new password

        # --- Server-Side Validation ---

        # 1. Basic Required Fields (excluding optional password)
        required_fields = {
            'First Name': first_name, 'Last Name': last_name, 'Date of Birth': dob_str,
            'Address': address, 'Station': station_id_str, 'Phone Number': phone_number_str,
            'Email': new_email, 'Username': new_username
        }
        for field_name, value in required_fields.items():
            if not value:
                return HttpResponse(f"<script>alert('Please fill the required field: {field_name}.'); window.history.back();</script>")

        # 2. Validate Date of Birth and Age (18-60)
        try:
            dob_date = datetime.strptime(dob_str, '%Y-%m-%d').date()
            today = date.today()

            if dob_date > today: # Prevent future dates
                return HttpResponse(f"<script>alert('Date of Birth cannot be in the future.'); window.history.back();</script>")

            age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
            
            if age < 18:
                return HttpResponse(f"<script>alert('Officer must be at least 18 years old.'); window.history.back();</script>")
            if age > 60:
                return HttpResponse(f"<script>alert('Officer cannot be older than 60 years.'); window.history.back();</script>")
            
            # If all DOB/age checks pass, assign the validated date object
            validated_dob = dob_date 
        except ValueError: # Catches errors from strptime if format is wrong
            return HttpResponse(f"<script>alert('Invalid Date of Birth format. Please use YYYY-MM-DD.'); window.history.back();</script>")

        # 3. Validate Username (if changed from original)
        if new_username.lower() != original_username.lower(): # Case-insensitive check for change
            if login_table.objects.filter(username__iexact=new_username).exclude(pk=officer.LOGIN.id).exists():
                return HttpResponse(f"<script>alert('This username ({new_username}) is already taken. Please choose another.'); window.history.back();</script>")
            if len(new_username) < 3: # Example: Minimum length check
                 return HttpResponse(f"<script>alert('Username must be at least 3 characters long.'); window.history.back();</script>")
            # If validation passes, the username will be updated on officer.LOGIN object later
        
        # 4. Validate and Convert Phone Number
        try:
            # Basic pattern check (can be more sophisticated if needed)
            if not (phone_number_str.isdigit() and len(phone_number_str) == 10 and phone_number_str[0] in ['6','7','8','9']):
                raise ValueError("Invalid phone number pattern.")
            validated_phone = int(phone_number_str)
        except ValueError:
            return HttpResponse(f"<script>alert('Invalid phone number format. Must be 10 digits starting with 6, 7, 8, or 9.'); window.history.back();</script>")

        # 5. Server-Side Email Uniqueness Check (if email was changed)
        if new_email != original_email.lower(): # Compare with normalized original
            if forest_officer.objects.filter(email__iexact=new_email).exclude(pk=id).exists():
                return HttpResponse(f"<script>alert('This email address ({new_email}) is already in use by another officer.'); window.history.back();</script>")
        
        # 6. Server-Side Phone Uniqueness Check (if phone was changed)
        if validated_phone != original_phone:
            if forest_officer.objects.filter(phone=validated_phone).exclude(pk=id).exists():
                return HttpResponse(f"<script>alert('This phone number ({validated_phone}) is already registered to another officer.'); window.history.back();</script>")

        # 7. Server-Side Station Assignment Check
        try:
            selected_station_id = int(station_id_str) if station_id_str else None
            validated_station_obj = None # Initialize
            
            if selected_station_id is None and original_station_id is not None: # Unassigning station
                validated_station_obj = None
            elif selected_station_id != original_station_id: # If the station is being changed or newly assigned
                if selected_station_id: # If a new station is actually selected (not empty choice)
                    # Check if this new station is already assigned to ANOTHER officer
                    if forest_officer.objects.filter(STATION_id=selected_station_id).exclude(pk=id).exists():
                        return HttpResponse(f"<script>alert('The selected station is already assigned to another officer. Please choose a different station.'); window.history.back();</script>")
                    validated_station_obj = get_object_or_404(forest_station, pk=selected_station_id)
                else: # This case should ideally be caught by "required field" if unassigning isn't allowed by clearing selection
                    return HttpResponse(f"<script>alert('Please select a valid station.'); window.history.back();</script>")
            else: # Station is not changing, keep existing
                 validated_station_obj = officer.STATION

        except ValueError: # For int(station_id_str)
            return HttpResponse(f"<script>alert('Invalid station ID submitted.'); window.history.back();</script>")
        except forest_station.DoesNotExist: # For get_object_or_404
            return HttpResponse(f"<script>alert('The selected station does not exist.'); window.history.back();</script>")

        # --- All server-side validations passed, proceed to update ---

        # Update officer's direct fields
        officer.first_name = first_name
        officer.last_name = last_name
        officer.dob = validated_dob # Use the validated date object
        officer.address = address
        officer.email = new_email # Use the (potentially normalized) new email
        officer.phone = validated_phone # Use the validated integer phone
        officer.STATION = validated_station_obj # Assign validated station object or None

        # Update Login Table (Username and Password)
        login_changed = False
        if new_username.lower() != original_username.lower():
            officer.LOGIN.username = new_username
            login_changed = True
        
        if password_new: # Only update password if a new one was actually entered
            if password_new != password_confirm:
                return HttpResponse(f"<script>alert('New passwords do not match. Please re-enter.'); window.history.back();</script>")
            # Add server-side complexity check for new_password here if desired (e.g., regex)
            # if not re.match(r"^(?=.*\d)(?=.*[\W_]).{8,}$", password_new):
            #    return HttpResponse(f"<script>alert('New password does not meet complexity requirements.'); window.history.back();</script>")
            officer.LOGIN.password = make_password(password_new)
            login_changed = True
        
        if login_changed:
            try:
                officer.LOGIN.save()
            except Exception as e:
                print(f"Error saving login for officer {officer.id}: {e}") # Server-side log
                return HttpResponse(f"<script>alert('Error updating login details: {str(e)}'); window.history.back();</script>")

        # Update Image (if a new one was uploaded)
        image_file = request.FILES.get('image_file')
        if image_file:
            fs = FileSystemStorage()
            # Optional: Delete old image if it exists
            if officer.image and officer.image.name: # Check if officer.image.name is not empty
                if fs.exists(officer.image.name):
                    try:
                        fs.delete(officer.image.name)
                    except Exception as e:
                        print(f"Warning: Error deleting old image '{officer.image.name}': {e}") # Log, but don't stop update

            try:
                # Save the new image
                file_name = fs.save(image_file.name, image_file)
                officer.image = file_name # Assign the path/name of the new image
            except Exception as e:
                print(f"Error uploading new image: {e}") # Server-side log
                return HttpResponse(f"<script>alert('Error uploading new image: {str(e)}'); window.history.back();</script>")

        # Save the updated Forest Officer object (which also saves foreign key changes like STATION)
        try:
            officer.save()
        except Exception as e:
            print(f"Error saving forest officer {officer.id}: {e}") # Server-side log
            return HttpResponse(f"<script>alert('An error occurred while updating the officer: {str(e)}'); window.history.back();</script>")

        # --- Redirect on success ---
        # Using reverse is good practice for URL management
        return HttpResponse(f"<script>alert('Forest Officer Updated Successfully!'); window.location.assign('{reverse('admin_view_forest_officer')}');</script>")

    else: # GET request - Display the form
        context = {
            'officer': officer,
            'stations': stations,
            'stations_with_other_officers_ids_js': stations_with_other_officers_ids,
        }
        return render(request, 'Admin/Edit_Forest_Officer.html', context)





def admin_delete_forest_officer(request, id):
    # Fetch the officer object. We use select_related to also fetch the login
    # object in the same database query for efficiency.
    officer = get_object_or_404(forest_officer.objects.select_related('LOGIN'), pk=id)

    # If the form on the confirmation page has been submitted
    if request.method == 'POST':
        # Store necessary info before deletion
        officer_name = f"{officer.first_name} {officer.last_name}"
        login_to_delete = officer.LOGIN  # Get a reference to the login object
        image_path = officer.image.path if officer.image else None

        try:
            # Use a transaction to ensure data integrity.
            # This means ALL operations inside this block must succeed.
            # If any operation fails, all previous ones are rolled back.
            with transaction.atomic():
                # 1. Delete the forest_officer object first.
                officer.delete()

                # 2. Explicitly delete the login_table object.
                if login_to_delete:
                    login_to_delete.delete()

            # 3. If the transaction was successful, delete the image file.
            if image_path:
                fs = FileSystemStorage()
                if fs.exists(image_path):
                    fs.delete(image_path)

            messages.success(request, f"Officer '{officer_name}' and their login account have been successfully deleted.")

        except Exception as e:
            # If anything went wrong, the transaction will be rolled back automatically.
            print(f"Error during officer deletion: {e}") # Log for debugging
            messages.error(request, f"An unexpected error occurred while trying to delete the officer. No data was changed.")

        # Redirect back to the officer list page
        return redirect('admin_view_forest_officer')

    # If it's a GET request, just display the confirmation page
    context = {
        'officer': officer
    }
    
    return render(request, 'Admin/Confirm_Delete_Forest_Officer.html', context)






# Entire views.py code block for Contacts Management-------------------:


# If you want ANYONE (even unauthenticated users) to view emergency contacts:
class EmergencyContactListView(generics.ListAPIView):
    queryset = contacts.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [permissions.AllowAny] # Or remove this line for default (IsAuthenticatedOrReadOnly)

# --- OR ---

# If you want ONLY AUTHENTICATED users (those logged in via RegularUserLogin) to view:
# class EmergencyContactListView(generics.ListAPIView):
#     queryset = contacts.objects.all()
#     serializer_class = ContactSerializer
#     permission_classes = [permissions.IsAuthenticated] # Ensures user is logged in

def admin_add_contacts(request):
    return render(request, 'Admin/Add_Contacts.html')

def check_phone_exists_contact(request):
    phone_str = request.GET.get('phone', None)
    contact_id = request.GET.get('contact_id', None) # NEW: Get officer_id
    is_taken = False

    if phone_str:
        try:
            phone_int = int(phone_str)
            query = contacts.objects.filter(phone=phone_int)
            if contact_id:
                try:
                    # Exclude the current officer being edited
                    query = query.exclude(pk=int(contact_id))
                except ValueError:
                    pass
            is_taken = query.exists()
        except ValueError:
            pass
    data = {
        'is_taken': is_taken
    }
    return JsonResponse(data)


def admin_add_contacts_post(request):
    if request.method == 'POST':
        # Assuming the form field names are 'name', 'details', 'phone'
        name = request.POST.get('name')
        details = request.POST.get('details')
        phone_str = request.POST.get('phone') # Get phone as string first

        if not name or not details or not phone_str:
             return HttpResponse('''<script> alert('All fields are required'); window.location='/admin_add_contacts'</script>''')

        try:
            # Convert phone string to integer
            phone = int(phone_str)
        except (ValueError, TypeError):
            return HttpResponse('''<script> alert('Invalid phone number format'); window.location='/admin_add_contacts'</script>''')


        obj = contacts()
        obj.name = name
        obj.details = details
        obj.phone = phone

        obj.save()

        return HttpResponse('''<script> alert('Contact Added'); window.location='/admin_view_contacts'</script>''')
    else:
         return HttpResponse("Method not allowed", status=405)


def admin_view_contacts(request):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        # Optionally, redirect officer to their home page if logged in but not admin
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # If checks pass, proceed with the view logic

    all_contacts = contacts.objects.all()
    search_term = '' # Initialize search_term

    if request.method == 'POST':
        # Handle search submission
        search_term = request.POST.get('search_query', '').strip() # Get the search text, remove leading/trailing spaces
        if search_term:
            # Filter officers by multiple fields (case-insensitive contains)
            # Using Q objects to combine conditions with OR
            filters = Q(name__icontains=search_term) | \
                      Q(details__icontains=search_term) | \
                      Q(phone__icontains=search_term)


            # Handle phone number search: try converting search_term to int
            try:
                search_phone = int(search_term)
                filters |= Q(phone=search_phone) # Add exact match for phone number if it's a number
            except ValueError:
                # If search_term is not a number, don't add phone filter
                pass

            all_contacts = contacts.objects.filter(filters)


    # Create the context dictionary
    context = {
        'all_contacts': all_contacts,
        'search_term': search_term # Pass the search term back to the template (optional)
    }

    return  render(request, 'Admin/View_Contacts.html', context)



def admin_edit_contacts(request, id):
    contact = get_object_or_404(contacts, id=id)
    if request.method == 'POST':
        contact.name = request.POST.get('name')
        contact.details = request.POST.get('details')
        contact.phone = request.POST.get('phone')
        contact.save()
        return HttpResponse('''<script> alert('Contact Updated'); window.location='/admin_view_contacts'</script>''')
    return render(request, 'Admin/Edit_Contacts.html', {'contact': contact})


def admin_delete_contacts(request, id):
    contact = get_object_or_404(contacts, id=id)
    contact.delete()
    return HttpResponse('''<script> alert('Contact Deleted'); window.location='/admin_view_contacts'</script>''')



# Entire views.py code block for View Feedback-------------------:

#android:####
@csrf_exempt
def send_feedback_api(request):
    print("--- Debug: Entered send_feedback_api view ---")

    if request.method == 'POST':
        print("--- Debug: Received POST request for feedback ---")
        try:
            print("--- Debug: Attempting to parse JSON body in send_feedback_api ---")
            data = json.loads(request.body)
            print(f"--- DEBUG: Successfully parsed JSON body: {data} ---")

            # --- Get data from the parsed JSON body ---
            user_login_id = data.get('user_login_id')
            # REMOVED: subject = data.get('subject') # Subject is optional based on Android code, but not in model
            message_text = data.get('message')
            # --- End Get data ---


            # --- Validation check using variables from JSON body ---
            if user_login_id is None or not message_text:
                 print("--- Debug: Missing user_login_id or message ---")
                 missing_fields = []
                 if user_login_id is None: missing_fields.append('user_login_id')
                 if not message_text: missing_fields.append('message')
                 return JsonResponse({'success': False, 'message': f'Missing required fields: {", ".join(missing_fields)}'}, status=400)
            # --- End Validation check ---


            try:
                print("--- Debug: Attempting to get user_table object using REGULAR_LOGIN__id in send_feedback_api ---")
                # Use user_login_id from JSON to find the user_table
                user = user_table.objects.get(REGULAR_LOGIN__id=user_login_id)
                print(f"--- Debug: Found user_table object for REGULAR_LOGIN__id: {user_login_id} (user_table id: {user.id}) ---")
            except user_table.DoesNotExist:
                print(f"--- Debug: User not found in user_table for REGULAR_LOGIN__id: {user_login_id} ---")
                return JsonResponse({'success': False, 'message': 'User profile not found for provided login ID'}, status=404)
            except Exception as e:
                 print(f"--- Debug: Error fetching user_table profile by REGULAR_LOGIN__id: {e} ---")
                 return JsonResponse({'success': False, 'message': 'Internal server error fetching user profile'}, status=500)

            # Create and save the feedback
            # --- MODIFIED: Use feedback_table and map message_text to details ---
            feedback = feedback_table(
                USER=user,
                details=message_text # Map the incoming 'message' to the 'details' field
            )
            # --- End MODIFIED ---
            feedback.save()
            print(f"--- Debug: Feedback saved successfully with ID: {feedback.id} ---")

            print("--- Debug: Returning successful JSON response from send_feedback_api ---")
            return JsonResponse({'success': True, 'message': 'Feedback submitted successfully!', 'feedback_id': feedback.id})

        except json.JSONDecodeError:
            print("--- DEBUG: JSONDecodeError caught in send_feedback_api ---")
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
             print(f"--- Debug: An unexpected error occurred in send_feedback_api POST block: {e} ---")
             return JsonResponse({'success': False, 'message': 'An error occurred while submitting feedback'}, status=500)

    else:
        print("--- Debug: Received non-POST request in send_feedback_api ---")
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'}, status=405)
# Android Code ENDS HERE:###########################

def admin_view_user_feedback(request):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        if request.session.get('user_type') == 'officer':
            return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page


    feedbacks = feedback_table.objects.all().order_by('-date')
    search_term = request.POST.get('search_query', '').strip() if request.method == 'POST' else ''

    if request.method == 'POST' and search_term:
        # Initialize an empty Q object to build combined filters
        combined_filters = Q()

        # 1. Add filters for the entire search_term (case-insensitive contains)
        # This covers single-word searches or exact matches of the full name
        if hasattr(feedback_table._meta.get_field('USER').remote_field.model, 'first_name'):
            combined_filters |= Q(USER__first_name__icontains=search_term)
        if hasattr(feedback_table._meta.get_field('USER').remote_field.model, 'last_name'):
            combined_filters |= Q(USER__last_name__icontains=search_term)
        # If your user_table has an email field, uncomment and use this:
        # if hasattr(feedback_table._meta.get_field('USER').remote_field.model, 'email'):
        #     combined_filters |= Q(USER__email__icontains=search_term)

        # Filter by feedback details content
        combined_filters |= Q(details__icontains=search_term)

        # 2. Handle multi-word search specifically for names
        # This logic triggers if the search term contains spaces,
        # allowing for searching "First Last" to find users where "First" is in
        # first_name/last_name AND "Last" is in first_name/last_name.
        if ' ' in search_term:
            keywords = search_term.split()
            name_part_filters = Q()
            for keyword in keywords:
                # For each keyword, build a Q object to check if it's in first_name OR last_name
                keyword_specific_q = Q()
                if hasattr(feedback_table._meta.get_field('USER').remote_field.model, 'first_name'):
                    keyword_specific_q |= Q(USER__first_name__icontains=keyword)
                if hasattr(feedback_table._meta.get_field('USER').remote_field.model, 'last_name'):
                    keyword_specific_q |= Q(USER__last_name__icontains=keyword)

                # Combine these keyword-specific Q objects with an AND operator.
                # This ensures ALL keywords must be present in some part of the user's name fields.
                name_part_filters &= keyword_specific_q if name_part_filters else keyword_specific_q

            # Add the multi-word name search to the main combined_filters using OR.
            # This means: (full search term match) OR (multi-word name match) OR (details match) OR (ID match)
            if name_part_filters: # Ensure name_part_filters was actually built
                 combined_filters |= name_part_filters

        # 3. Handle numeric search for User ID (exact match)
        try:
            search_user_id_int = int(search_term)
            combined_filters |= Q(USER__id=search_user_id_int)
        except ValueError:
            # If search_term is not a valid integer, this part of the filter is skipped
            pass

        # Apply all constructed filters and ensure distinct results
        feedbacks = feedback_table.objects.filter(combined_filters).distinct().order_by('-date')

    context = {
        'feedbacks': feedbacks,
        'search_query': search_term, # Pass search_term back to template for the input field
    }
    # Ensure you are rendering the correct template
    return render(request, 'Admin/View_User_Feedback.html', context)



def admin_feedback_detail(request, feedback_id):
    # Use get_object_or_404 to retrieve the object or return a 404 error if not found
    feedback = get_object_or_404(feedback_table, pk=feedback_id)
    context = {'feedback': feedback}
    return render(request, 'Admin/Feedback_Detail.html', context)

def admin_delete_user_feedback(request, id):
    """
    View to delete a specific user feedback.
    Handles deletion via POST request and redirects.
    """
    # Get the feedback object or return 404 if not found
    feedback = get_object_or_404(feedback_table, pk=id)

    # Only allow POST requests for deletion
    # if request.method == 'POST':
    feedback.delete()
    # Redirect to the feedback list page after deletion
    return redirect('admin_view_user_feedback')
    # else:
    #     # Optionally, handle GET request (e.g., return an error or redirect)
    #     # For this case, we'll just redirect back to the list if it's not POST
    #     return redirect('admin_view_user_feedback')

# Entire views.py code block for Send Notification To Forest Officer-------------------:

def admin_send_notification_to_officer(request):

    
    # Get current date and time
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d") # Format date as YYYY-MM-DD for input value
    current_time = now.strftime("%H:%M:%S") # Format time as HH:MM:SS

    # Pass date and time to the template context
    context = {
        'current_date': current_date,
        'current_time': current_time,
    }
    return render(request, 'Admin/Send_Notification_To_Officer.html', context)


def admin_send_notification_to_officer_post(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('notification_file')
        custom_file_name = request.POST.get('custom_file_name', '').strip() # Get the custom name

        if not uploaded_file:
            # Using Django messages framework is better than JS alerts
            messages.error(request, 'No file uploaded. Please select a file.')
            return redirect('admin_send_notification_to_officer')

        try:
            obj = admin_notification()
            obj.notification = uploaded_file
            obj.date = date.today()
            # obj.time is set by auto_now_add=True on model field
            
            if custom_file_name: # Save custom name if provided
                obj.display_name = custom_file_name
            # If no custom name, display_name will remain blank/null

            obj.save()
            messages.success(request, 'Notification sent successfully!')
            return redirect('admin_view_notification_to_officer')

        except Exception as e:
            print(f"Error saving notification: {e}")
            messages.error(request, f'An error occurred while sending the notification: {e}')
            return redirect('admin_send_notification_to_officer')
    else:
        # This view should only be accessed via POST from the form
        return redirect('admin_send_notification_to_officer')



def admin_view_notification_to_officer(request):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        if request.session.get('user_type') == 'officer':
            return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login'))

    all_notifications = admin_notification.objects.all().order_by('-date', '-time') # Order by most recent
    search_query = request.GET.get('search_query', '')

    if search_query:
        all_notifications = all_notifications.filter(
            Q(display_name__icontains=search_query) |  # Search in custom display name
            Q(notification__icontains=search_query)    # Search in original filename
        )

    context = {
        'all_notifications': all_notifications,
        'search_query': search_query, # Pass search query back for form repopulation
    }
    return render(request, 'Admin/View_Notification_to_Officer.html', context)

def admin_delete_notification_to_officer(request, id):
    notification = get_object_or_404(admin_notification, pk=id)
    # Consider adding a confirmation step or ensuring it's a POST request for safety
    notification_name = notification.display_name or notification.notification.name.split('/')[-1]
    notification.delete()
    messages.success(request, f"Notification '{notification_name}' deleted successfully.")
    return redirect('admin_view_notification_to_officer')




# Entire views.py code block for View Forest Officer Reports-------------------:


def admin_view_officer_report(request):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        # Optionally, redirect officer to their home page if logged in but not admin
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # If checks pass, proceed with the view logic



    reports = daily_reports.objects.all()
    context = {'reports': reports}
    return  render(request, 'Admin/View_Officer_Report.html', context)

def admin_delete_officer_report(request, id):
    report = get_object_or_404(daily_reports, pk=id)
    report.delete()
    return redirect('admin_view_officer_report')



# Entire views.py code block for Animal Management---------------(working)----:

def admin_add_animal(request):
    a=animal.objects.all()
    return render(request, 'Admin/Add_Animal.html')

def check_animal_exists(request):
    animal_name = request.GET.get('name', None)
    data = {'exists': False} # Default response
    if request.method == 'GET' and animal_name:
        # Case-insensitive check is generally better for user-facing name uniqueness
        # The model already has unique=True, but this provides live feedback.
        # If unique=True is case-sensitive at DB level (depends on DB), 
        # then this check should align (e.g. name=animal_name).
        # For user-friendly uniqueness, iexact is common.
        if animal.objects.filter(name__iexact=animal_name).exists():
            data['exists'] = True
        return JsonResponse(data)
    
    # If not a GET request or name not provided, could return an error or default
    # For simplicity here, if name is not provided, it will imply exists=False,
    # but the JS client should ensure name is non-empty before calling.
    # Or, to be more explicit:
    if not animal_name:
        return JsonResponse({'error': 'Name parameter not provided'}, status=400)
        
    return JsonResponse(data) # Fallback, though ideally covered by above conditions

def admin_add_animal_post(request):
    if request.method == 'POST':
        # Get data from POST request using the correct 'name' attributes from Add_Animal.html
        name_val = request.POST.get('name')
        details_val = request.POST.get('details')
        type_val = request.POST.get('type')
        image_file = request.FILES.get('image')

        # --- Server-side validation ---
        errors = []
        if not name_val:
            errors.append("Name is required.")
        # The pattern in HTML is ^[a-zA-Z\s]+$
        elif not name_val.replace(" ", "").isalpha() and not all(c.isalpha() or c.isspace() for c in name_val):
             errors.append("Name can only contain letters and spaces.")
        
        if not details_val:
            errors.append("Details are required.")
            
        if not type_val:
            errors.append("Type is required.")
        
        # Check for existing animal name (case-insensitive is usually user-friendly)
        # This is a server-side check that complements the client-side AJAX validation
        # and the database's `unique=True` constraint on the model.
        if name_val and animal.objects.filter(name__iexact=name_val).exists():
            errors.append(f"An animal with the name '{name_val}' already exists. Please choose a different name.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('admin_add_animal_page') 

        # --- If validation passes, create and save the animal ---
        try:
            new_animal = animal()
            new_animal.name = name_val
            new_animal.details = details_val
            new_animal.type = type_val
            
            if image_file:
                new_animal.image = image_file

            new_animal.save()
            messages.success(request, f"Animal '{new_animal.name}' added successfully!")
            return redirect('admin_view_animal') 
        
        except Exception as e:
            
            print(f"Error saving animal: {e}") # For development, log properly in production
            messages.error(request, f"An unexpected error occurred while adding the animal. Please try again.")
            return redirect('admin_add_animal_page') # Redirect back to the form

    else:
        # If the request is not POST, redirect to the form page
        messages.warning(request, "Invalid request. Please submit the form.")
        return redirect('admin_add_animal_page')


def admin_view_animal(request):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        # Optionally, redirect officer to their home page if logged in but not admin
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # If checks pass, proceed with the view logic


    animals = animal.objects.all()
    search_term = ''  # Initialize search_term

    if request.method == 'POST':
        # Handle search submission
        search_term = request.POST.get('textfield', '').strip()  # Get the search text, remove leading/trailing spaces
        if search_term:
            # Filter stations by name (case-insensitive contains)
            animals = animals.filter(
                Q(name__icontains=search_term) |
                Q(type__icontains=search_term)  # Search in the related Division's name
            )
    # Create the context dictionary
    context = {'animals': animals,
               'search_term': search_term  # Pass the search term back to the template (optional, but good practice)
               }
    return  render(request, 'Admin/View_Animals.html', context)


def admin_edit_animal(request, id):
    # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login'))

    animal_obj = get_object_or_404(animal, id=id)

    if request.method == 'POST':
       
        # Only update the name if it's NOT a core animal.
        # The template should make the name field readonly for core animals,
        # but this backend check is a safety measure.
        if not animal_obj.is_core_animal:
            new_name = request.POST.get('textfield3')
            if new_name: # Ensure a name is provided if it's being changed
                animal_obj.name = new_name
            else:
                # Handle error: non-core animal name cannot be empty if required by model
                return HttpResponse('''<script> alert('Name cannot be empty for this animal.'); window.history.back();</script>''')
        # If it's a core animal, animal_obj.name is NOT updated from POST, effectively keeping it unchanged.

        animal_obj.details = request.POST.get('textfield', animal_obj.details)
        animal_obj.type = request.POST.get('select', animal_obj.type)

        image_file = request.FILES.get('file', None)

        if image_file:
            fs = FileSystemStorage()
            if animal_obj.image and animal_obj.image.name: # Check if image field has a value
                old_image_path = os.path.join(settings.MEDIA_ROOT, str(animal_obj.image.name))
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                        print(f"Deleted old image: {animal_obj.image.name}")
                    except Exception as e:
                        print(f"Error deleting old image {animal_obj.image.name}: {e}")

            try:
                # Define a unique path or let Django handle it with upload_to in model
                # Using 'animal_images/' as a subdirectory if configured in FileField's upload_to
                file_path = fs.save(os.path.join('animal_images', image_file.name), image_file)
                animal_obj.image = file_path # Update the image field
            except Exception as e:
                print(f"Error saving new image: {e}")
                return HttpResponse(f'''<script> alert('Error saving new image: {e}'); window.history.back();</script>''')

        # Validate required fields (details and type might also be required by your model)
        if not animal_obj.details: # Add other required field checks if necessary
             return HttpResponse('''<script> alert('Details field cannot be empty.'); window.history.back();</script>''')
        if not animal_obj.type:
             return HttpResponse('''<script> alert('Type field must be selected.'); window.history.back();</script>''')

        try:
            animal_obj.save()
            return HttpResponse('''<script> alert('Animal Updated'); window.location='/admin_view_animal/'</script>''')
        except Exception as e:
             print(f"Error saving animal object: {e}")
             return HttpResponse(f'''<script> alert('Error updating animal: {e}'); window.history.back();</script>''')
    else:
        context = {'animal': animal_obj}
        return render(request, 'Admin/Edit_Animal.html', context)


def admin_delete_animal(request, id):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login'))

    animal_obj = get_object_or_404(animal, id=id)

    # --- MODIFICATION START for is_core_animal ---
    if animal_obj.is_core_animal:
        # Prevent deletion of core animals
        return HttpResponse('''<script> alert('This is a core animal and cannot be deleted.'); window.location='/admin_view_animal/'</script>''')
    # --- MODIFICATION END ---

    # Proceed with deletion only if not a core animal
    if animal_obj.image and animal_obj.image.name: # Check if image field has a value
        image_path = os.path.join(settings.MEDIA_ROOT, str(animal_obj.image.name))
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"Deleted image: {animal_obj.image.name}")
            except Exception as e:
                print(f"Error deleting image {animal_obj.image.name} for animal ID {animal_obj.id}: {e}")

    try:
        animal_obj.delete()
        return HttpResponse('''<script> alert('Animal Deleted'); window.location='/admin_view_animal/'</script>''')
    except Exception as e:
        print(f"Error deleting animal object ID {animal_obj.id}: {e}")
        return HttpResponse(f'''<script> alert('Error deleting animal: {e}'); window.history.back();</script>''')



# Entire views.py code block for Camera Management-------------------:

def admin_add_camera(request):
    return render(request, 'Admin/Add_Camera_Admin.html')

def admin_add_camera_post(request):
    camera_id = request.POST.get('camera_no')  # Field for camera id
    latitude = request.POST.get('latitude')  # Field for camera location
    longitude = request.POST.get('longitude')  # Field for camera location
    obj = camera()
    obj.camera_id = camera_id
    obj.latitude = latitude
    obj.longitude = longitude
    obj.save()

    return HttpResponse('''<script> alert('Camera Added'); window.location='/admin_view_camera'</script>''')

def admin_view_camera(request):
        # Check if user is authenticated and is an admin
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        # Redirect to login if not authenticated or not admin
        # Optionally, redirect officer to their home page if logged in but not admin
        if request.session.get('user_type') == 'officer':
             return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # If checks pass, proceed with the view logic
    cameras = camera.objects.all()
    context = {'cameras': cameras}
    return  render(request, 'Admin/View_Camera_Admin.html', context)

def admin_edit_camera(request, id):
    # Get the camera object or return 404 if not found
    camera_obj = get_object_or_404(camera, id=id)

    if request.method == 'POST':
        # Handle the form submission for editing
        camera_id_str = request.POST.get('camera_no', None)
        latitude_str = request.POST.get('latitude', None)
        longitude_str = request.POST.get('longitude', None)

        # Basic validation and type conversion
        try:
            # Use existing value as default if post data is None
            camera_obj.camera_id = int(camera_id_str) if camera_id_str else camera_obj.camera_id
            camera_obj.latitude = float(latitude_str) if latitude_str else camera_obj.latitude
            camera_obj.longitude = float(longitude_str) if longitude_str else camera_obj.longitude
        except (ValueError, TypeError):
            return HttpResponse('''<script> alert('Invalid number format for Camera ID, Latitude, or Longitude.'); window.history.back();</script>''')

        # Check if required fields became None after conversion (shouldn't happen with defaults, but good check)
        if camera_obj.camera_id is None or camera_obj.latitude is None or camera_obj.longitude is None:
             return HttpResponse('''<script> alert('Required fields cannot be empty.'); window.history.back();</script>''')


        try:
            camera_obj.save() # Save the updated object
            return HttpResponse('''<script> alert('Camera Updated'); window.location='/admin_view_camera/'</script>''') # Redirect to view list
        except Exception as e:
             print(f"Error saving camera object: {e}")
             return HttpResponse(f'''<script> alert('Error updating camera: {e}'); window.history.back();</script>''')

    else:
        # Render the edit form with existing data
        context = {'camera': camera_obj}
        return render(request, 'Admin/Edit_Camera.html', context)


def admin_delete_camera(request, id):
    # Get the camera object or return 404 if not found
    camera_obj = get_object_or_404(camera, id=id) # Fetched object is camera_obj

    # No associated files to delete for the camera model

    try:
        # Correct variable name here: delete camera_obj
        camera_obj.delete()
        return HttpResponse('''<script> alert('Camera Deleted'); window.location='/admin_view_camera/'</script>''') # Redirect to view list
    except Exception as e:
        print(f"Error deleting camera object: {e}")
        return HttpResponse(f'''<script> alert('Error deleting camera: {e}'); window.history.back();</script>''')







# Entire views.py code block for Camera Alerts-------------------:

def admin_add_camera_alerts(request):
    # This view is for manually adding alerts via a form.
    # It remains as is if you want to keep that manual functionality.
    cameras = camera.objects.all()
    animals = animal.objects.all()
    return render(request, 'Admin/Add_Camera_Alerts.html', {'cameras': cameras, 'animals': animals})

def admin_add_camera_alerts_post(request):
    # This is the placeholder for handling the POST request from the manual add form.
    # You would add logic here to create a camera_alerts object based on form data.
    pass # Add your POST handling logic here if needed

def admin_view_camera_alerts(request):
    # This view will fetch and display the automatic camera alerts from the database

    # Fetch all camera alerts with select_related for related CAMERA, STATION, and ANIMAL
    alerts = camera_alerts.objects.select_related('CAMERA', 'CAMERA__station', 'ANIMAL').all().order_by('-date', '-time')

    # Create a context dictionary to pass the data to the template
    context = {
        'alerts': alerts
    }

    # Render the template, passing the alerts data
    return render(request, 'Admin/View_Camera_Alerts.html', context)

def admin_edit_camera_alerts(request, id):
    # Get the specific camera alert object, or return a 404 if it doesn't exist
    alert = get_object_or_404(camera_alerts, id=id)

    if request.method == 'POST':
        # If the request is POST, process the form data
        form = CameraAlertForm(request.POST, request.FILES, instance=alert)
        if form.is_valid():
            form.save()
            # Redirect to the view alerts page after successful edit
            return redirect('admin_view_camera_alerts')
    else:
        # If the request is GET, display the form with the current alert data
        form = CameraAlertForm(instance=alert)

    # Render the edit template, passing the form and the alert object
    return render(request, 'Admin/Edit_Camera_Alerts.html', {'form': form, 'alert': alert})


def admin_delete_camera_alerts(request, id):
    # Get the specific camera alert object, or return a 404 if it doesn't exist
    alert = get_object_or_404(camera_alerts, id=id)

    if request.method == 'POST':
        # If the request is POST, delete the alert
        alert.delete()
        # Redirect to the view alerts page after successful deletion
        return redirect('admin_view_camera_alerts')

    # If the request is GET, you might want to show a confirmation page
    # For simplicity, this example assumes a POST request for deletion (e.g., from a form or button)
    # If you want a confirmation page, render a template here.
    # return render(request, 'Admin/Confirm_Delete_Camera_Alert.html', {'alert': alert})

# Note: You'll need to create a forms.py file and a CameraAlertForm
# Also, create Edit_Camera_Alerts.html and optionally Confirm_Delete_Camera_Alert.html templates



def admin_bulk_delete_camera_alerts(request):
    # This view handles the POST request for deleting multiple alerts

    if request.method == 'POST':
        # Get the list of selected alert IDs from the form data
        # request.POST.getlist('selected_alerts') gets all values for checkboxes named 'selected_alerts'
        selected_alert_ids = request.POST.getlist('selected_alerts')

        if selected_alert_ids:
            # Convert IDs to integers (they come as strings from POST data)
            # and filter out any potential empty strings
            selected_ids = [int(id) for id in selected_alert_ids if id.isdigit()]

            if selected_ids:
                # Delete the selected alerts efficiently using the ORM
                # __in looks for objects whose 'id' is in the list of selected_ids
                delete_count, _ = camera_alerts.objects.filter(id__in=selected_ids).delete()

                # Optional: Add a success message (requires Django messaging framework)
                # from django.contrib import messages
                # messages.success(request, f"{delete_count} alerts deleted successfully.")

        # Redirect back to the view alerts page after deletion
        return redirect('admin_view_camera_alerts')
    else:
        # If it's not a POST request, redirect or return an error
        # Bulk deletion should only happen via POST
        # return HttpResponse("Method not allowed", status=405) # Or redirect
        return redirect('admin_view_camera_alerts') # Redirect back if someone tries a GET request






#useful incase we want to add this functionality for Admin
def admin_add_dangerous_area(request):
    return render(request, 'Admin/Add_Dangerous_Area.html')


#FOREST OFFICER PAGE----------------------------------------------------------

# Entire views.py code block for Camera Management-------------------:


# --- Corrected Forest Officer Views ---

@never_cache
def forest_officer_add_camera(request): # This is your GET view
    if not request.session.get('is_authenticated'):
        messages.error(request, "Authentication required.")
        return redirect(reverse('login'))
    if request.session.get('user_type') != 'officer':
        messages.error(request, "Access denied. Officer access required.")
        return redirect(reverse('admin_home') if request.session.get('user_type') == 'admin' else reverse('login'))

    # For GET, fetch officer_station to potentially pass to form or context
    officer_station_for_form_init = None
    station_error_msg_for_get = None
    try:
        login_id = request.session.get('user_id')
        officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=login_id)
        officer_station_for_form_init = officer.STATION
        if not officer_station_for_form_init:
            station_error_msg_for_get = "Your officer profile is not assigned to a station. Cannot add camera effectively."
            messages.warning(request, station_error_msg_for_get) # Warn but still show form
    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found.")
        return redirect(reverse('login')) # Critical error, redirect
    except Exception as e:
        messages.error(request, f"Error fetching officer details: {e}")
        print(f"Error fetching officer details in GET add_camera: {e}")
        return redirect(reverse('forest_officer_home'))


    # Pass station to the form. It might not use it on GET, but good for consistency
    # if the form's __init__ were to do something with it immediately.
    form = CameraForm(station=officer_station_for_form_init) 
    context = {
        'form': form,
        'initial_map_lat': 9.9312,
        'initial_map_lon': 76.2673,
        'initial_map_zoom': 7,
        'station_error_message': station_error_msg_for_get # Pass the error message
    }
    return render(request, 'Forest Officer/Add_Camera.html', context)

@never_cache
def forest_officer_add_camera_post(request):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        return redirect(reverse('login') if request.session.get('user_type') != 'admin' else reverse('admin_home'))

    if request.method != 'POST':
        return redirect(reverse('forest_officer_add_camera'))

    officer_station = None # Initialize
    try:
        login_id = request.session.get('user_id')
        if not login_id:
            messages.error(request, "Session error: User ID not found. Please log in again.")
            return redirect(reverse('login'))

        officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=login_id)
        officer_station = officer.STATION
        if not officer_station:
            # Instantiate form first to add a non-field error if no station
            form = CameraForm(request.POST, station=None) # Pass None, validation will catch it or we add error
            form.add_error(None, "Cannot add camera: Your officer profile is not assigned to a station.")
            # Proceed to render form with this error (will skip is_valid)
        else:
            # Pass the fetched officer_station to the form for validation
            form = CameraForm(request.POST, station=officer_station)

    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found. Please log in again.")
        return redirect(reverse('login'))
    except Exception as e:
        print(f"Error fetching officer/station in add_camera_post: {e}")
        messages.error(request, f"An unexpected error occurred fetching your details: {e}")
        # Instantiate a dummy form to pass to context if error happens before form instantiation
        form = CameraForm(request.POST, station=None) # Pass dummy station
        form.add_error(None, f"An unexpected server error occurred. Please try again.")


    # Check if officer_station was successfully retrieved and then if form is valid
    if officer_station and form.is_valid():
        new_camera = form.save(commit=False)
        new_camera.station = officer_station # Assign the officer's station
        try:
            new_camera.save()
            messages.success(request, f"Camera {new_camera.camera_id} added successfully to station '{officer_station.name}'!")
            return redirect(reverse('forest_officer_view_camera'))
        except Exception as e:
            print(f"Error saving camera instance: {e}")
            messages.error(request, f"Could not save camera due to a server error: {e}")
            form.add_error(None, "An unexpected error occurred while saving the camera. Please try again.")
    # else:
    #     # Form is invalid, or officer_station was None and an error was added to the form.
    #     if not any(messages.get_messages(request)) and (form.errors or not officer_station):
    #          messages.error(request, "Please correct the errors highlighted below.")

    # Common context preparation for re-rendering the form
    context = {'form': form}
    if form.is_bound:
        try:
            lat_val = form.cleaned_data.get('latitude', float(request.POST.get('latitude', '')))
            lon_val = form.cleaned_data.get('longitude', float(request.POST.get('longitude', '')))
            context['initial_map_lat'] = lat_val
            context['initial_map_lon'] = lon_val
            context['initial_map_zoom'] = 13
        except (ValueError, TypeError): # Handle cases where POST data isn't floatable or cleaned_data not there
            context['initial_map_lat'] = 9.9312
            context['initial_map_lon'] = 76.2673
            context['initial_map_zoom'] = 7
    else:
        context['initial_map_lat'] = 9.9312
        context['initial_map_lon'] = 76.2673
        context['initial_map_zoom'] = 7
    
    if not officer_station: # Ensure error message is in context if station was the issue
        context['station_error_message'] = "Your officer profile is not assigned to a station. Cannot add camera."


    return render(request, 'Forest Officer/Add_Camera.html', context)



def forest_officer_view_camera(request):
    # Check if user is authenticated and is an officer
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        # if request.session.get('user_type') == 'admin': # Assuming you have admin_home
        #     return redirect(reverse('admin_home'))
        # else:
        return redirect(reverse('login')) # Ensure 'login' is a valid URL name

    login_id = request.session.get('user_id')
    if not login_id:
         messages.error(request, 'Session error: User ID not found.')
         return redirect(reverse('login'))

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station = officer.STATION
    except ObjectDoesNotExist:
         messages.error(request, 'Officer profile not found for the logged-in user.')
         return redirect(reverse('login'))
    except Exception as e:
         print(f"Error retrieving officer/station: {e}")
         messages.error(request, 'An error occurred retrieving officer details.')
         return redirect(reverse('forest_officer_home')) # Or a suitable error page

    # --- Filter cameras by the officer's station ---
    # Also handle the search functionality if a search term is provided
    search_query = request.POST.get('textfield', '').strip() # Get search term from POST
    
    cameras_qs = camera.objects.filter(station=officer_station)
    if search_query:
        try:
            search_id = int(search_query)
            cameras_qs = cameras_qs.filter(camera_id=search_id) # Filter by camera_id field
            if not cameras_qs.exists():
                messages.info(request, f"No camera found with device ID: {search_id} in your station.")
        except ValueError:
            messages.error(request, "Invalid camera ID for search. Please enter a number.")
            # Show all cameras for the station if search is invalid
    
    cameras_list = list(cameras_qs) # Evaluate the queryset

    context = {
        'cameras': cameras_list,
        'web_launcher_url': WEB_LAUNCHER_URL, # Add launcher URL to context
        'search_query': search_query # Pass back the search query for the input field
    }
    return render(request, 'Forest Officer/View_Camera.html', context)


def forest_officer_edit_camera(request, id): # 'id' here is camera.id (PK)
    # Authentication and authorization
    if not request.session.get('is_authenticated'):
        messages.error(request, "Authentication required.")
        return redirect(reverse('login'))
    if request.session.get('user_type') != 'officer':
        messages.error(request, "Access denied. Officer access required.")
        return redirect(reverse('admin_home') if request.session.get('user_type') == 'admin' else reverse('login'))

    login_id = request.session.get('user_id')
    try:
        officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=login_id)
        officer_station = officer.STATION
        if not officer_station:
            messages.error(request, "Cannot edit camera: Your profile is not assigned to a station.")
            return redirect(reverse('forest_officer_view_camera')) # Or officer home
    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found.")
        return redirect(reverse('login'))
    except Exception as e:
        messages.error(request, f"An error occurred fetching your details: {e}")
        print(f"Error fetching officer/station in edit_camera: {e}")
        return redirect(reverse('forest_officer_view_camera'))


    # Get the camera object, ensuring it belongs to the officer's station
    # This also prevents editing cameras if officer has no station (officer_station would be None)
    camera_instance = get_object_or_404(camera, id=id, station=officer_station)

    if request.method == 'POST':
        # Pass instance for editing, and station for validation context
        form = CameraForm(request.POST, instance=camera_instance, station=officer_station)
        if form.is_valid():
            try:
                updated_camera = form.save(commit=False)
                # Station is already set on camera_instance and shouldn't change unless form allows it
                # If you allow changing station via form, that logic would be here
                updated_camera.save()
                messages.success(request, f"Camera {updated_camera.camera_id} updated successfully!")
                return redirect(reverse('forest_officer_view_camera'))
            except Exception as e:
                print(f"Error saving updated camera: {e}")
                messages.error(request, f"Could not update camera: {e}")
                form.add_error(None, f"An unexpected error occurred while saving: {e}")
        else:
            # Form is invalid
            messages.error(request, "Please correct the errors highlighted below.")
    else: # GET request
        # Pre-populate form with camera_instance data and pass station for context
        form = CameraForm(instance=camera_instance, station=officer_station)

    context = {'form': form, 'camera': camera_instance} # Pass camera_instance for titles etc.
    # For map re-initialization with existing/submitted values
    if form.is_bound: # If form was submitted (POST) and is being re-rendered due to errors
        try:
            context['initial_map_lat'] = form.cleaned_data.get('latitude', float(request.POST.get('latitude', camera_instance.latitude)))
            context['initial_map_lon'] = form.cleaned_data.get('longitude', float(request.POST.get('longitude', camera_instance.longitude)))
            context['initial_map_zoom'] = 13
        except (ValueError, TypeError):
            context['initial_map_lat'] = camera_instance.latitude if camera_instance.latitude is not None else 9.9312
            context['initial_map_lon'] = camera_instance.longitude if camera_instance.longitude is not None else 76.2673
            context['initial_map_zoom'] = 13 if camera_instance.latitude is not None else 7
    else: # GET request, pre-fill map with existing camera location
        context['initial_map_lat'] = camera_instance.latitude if camera_instance.latitude is not None else 9.9312
        context['initial_map_lon'] = camera_instance.longitude if camera_instance.longitude is not None else 76.2673
        context['initial_map_zoom'] = 13 if camera_instance.latitude is not None else 7
        
    return render(request, 'Forest Officer/Edit_Camera.html', context)

def forest_officer_delete_camera(request, id): # id is camera.id (PK)
    # 1. Authentication and Authorization
    if not request.session.get('is_authenticated'):
        messages.error(request, "Authentication required.")
        return redirect(reverse('login'))
    if request.session.get('user_type') != 'officer':
        messages.error(request, "Access denied. Officer access required.")
        return redirect(reverse('admin_home') if request.session.get('user_type') == 'admin' else reverse('login'))

    login_id = request.session.get('user_id')
    officer_station = None
    try:
        officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=login_id)
        officer_station = officer.STATION
        if not officer_station:
            messages.error(request, "Cannot manage cameras: Your profile is not assigned to a station.")
            return redirect(reverse('forest_officer_view_camera')) # Or officer home
    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found.")
        return redirect(reverse('login'))
    except Exception as e:
        messages.error(request, f"An error occurred fetching your details: {e}")
        print(f"Error fetching officer/station in delete_camera: {e}")
        return redirect(reverse('forest_officer_view_camera')) # Redirect to a safe page

    # 2. Get the camera object, ensuring it belongs to the officer's station
    camera_instance = get_object_or_404(camera, id=id, station=officer_station)

    if request.method == 'POST':
        # This is the actual deletion confirmed by the user
        try:
            camera_id_display = camera_instance.camera_id # Get ID for message before deleting
            camera_instance.delete()
            messages.success(request, f"Camera (Device ID: {camera_id_display}) has been deleted successfully.")
            return redirect(reverse('forest_officer_view_camera'))
        except Exception as e:
            print(f"Error deleting camera object (ID: {id}): {e}")
            messages.error(request, f"An error occurred while trying to delete the camera: {e}")
            # Redirect back to the view camera page, or the confirmation page with an error
            # For simplicity, redirecting to view camera. The error message will be shown there.
            return redirect(reverse('forest_officer_view_camera'))
    else: # GET request
        # Display the confirmation page
        context = {'camera': camera_instance}
        return render(request, 'Forest Officer/Confirm_Delete_Camera.html', context)


def view_my_webcam(request):
    return render(request, 'Forest Officer/view_my_webcam.html')

# Entire views.py code block for Camera Alerts-------------------:

# --- Modified Camera Alerts Views ---

def forest_officer_add_camera_alerts(request):
    # Check if user is authenticated and is an officer
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        if request.session.get('user_type') == 'admin':
            # Redirect admin to login? Or admin home? Let's follow your pattern and redirect non-officer to login
            return redirect(reverse('login'))
        else:
            return redirect(reverse('login')) # Or redirect to an 'unauthorized' page

    # Get the logged-in officer's station to filter cameras for the form
    # *** Use 'user_id' from session ***
    login_id = request.session.get('user_id')
    if not login_id:
         return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station = officer.STATION
    except ObjectDoesNotExist:
         return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
         print(f"Error retrieving officer/station: {e}")
         return HttpResponse('''<script> alert('An error occurred finding officer station.'); window.history.back();</script>''')

    # --- Filter cameras by the officer's station ---
    # This ensures the dropdown only shows cameras for their station
    cameras_for_station = camera.objects.filter(station=officer_station)
    # ---------------------------------------------

    # Get all animals (assuming animals are not station-specific)
    animals = animal.objects.all()

    # You might want to pass a form instance if using ModelForms for manual add
    # form = ManualCameraAlertForm() # You might need a separate form for manual add
    # Pass the filtered cameras to the template
    return render(request, 'Forest Officer/Add_Camera_Alerts.html', {'cameras': cameras_for_station, 'animals': animals})


def forest_officer_add_camera_alerts_post(request):
    # Check if user is authenticated and is an officer
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        if request.session.get('user_type') == 'admin':
            return redirect(reverse('login'))
        else:
            return redirect(reverse('login'))

    # *** Use 'user_id' from session ***
    login_id = request.session.get('user_id')
    if not login_id:
         return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station = officer.STATION
    except ObjectDoesNotExist:
         return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
         print(f"Error retrieving officer/station: {e}")
         return HttpResponse('''<script> alert('An error occurred finding officer station.'); window.history.back();</script>''')

    if request.method == 'POST':
        # Assuming your manual add form posts camera_id, animal_id, image, date, time
        camera_id = request.POST.get('camera') # Assuming name='camera' for camera select
        animal_id = request.POST.get('animal') # Assuming name='animal' for animal select
        # Get other fields like image, date, time from request.POST and request.FILES

        # --- Validation: Ensure the selected camera belongs to the officer's station ---
        if not camera_id:
            return HttpResponse('''<script> alert('Camera not selected.'); window.history.back();</script>''')
        try:
            # Get the camera object, ensuring it belongs to the officer's station
            selected_camera = get_object_or_404(camera, id=camera_id, station=officer_station)
        except Exception as e:
             print(f"Error fetching selected camera: {e}")
             return HttpResponse('''<script> alert('Invalid camera selected or you do not have permission for this camera.'); window.history.back();</script>''')
        # --------------------------------------------------------------------------

        # --- Get Animal object ---
        if not animal_id:
            return HttpResponse('''<script> alert('Animal not selected.'); window.history.back();</script>''')
        try:
            selected_animal = get_object_or_404(animal, id=animal_id)
        except Exception as e:
             print(f"Error fetching selected animal: {e}")
             return HttpResponse('''<script> alert('Invalid animal selected.'); window.history.back();</script>''')
        # -------------------------

        # --- Get Image, Date, Time ---
        alert_image = request.FILES.get('image') # Assuming name='image' for file input
        alert_date_str = request.POST.get('date') # Assuming name='date' for date input
        alert_time_str = request.POST.get('time') # Assuming name='time' for time input

        # Basic validation for other fields
        if not alert_image or not alert_date_str or not alert_time_str:
             return HttpResponse('''<script> alert('Image, Date, and Time are required.'); window.history.back();</script>''')

        # Convert date and time strings to Python objects (requires error handling)
        from datetime import datetime
        try:
            alert_date = datetime.strptime(alert_date_str, '%Y-%m-%d').date() # Adjust format if needed
            alert_time = datetime.strptime(alert_time_str, '%H:%M').time() # Adjust format if needed
        except ValueError:
             return HttpResponse('''<script> alert('Invalid Date or Time format.'); window.history.back();</script>''')
        # -----------------------------

        # --- Create and Save Camera Alert Object ---
        try:
            alert = camera_alerts.objects.create(
                CAMERA=selected_camera,
                ANIMAL=selected_animal,
                image=alert_image,
                date=alert_date,
                time=alert_time
                # created_at is auto_now_add
            )
            alert.save()
            return HttpResponse('''<script> alert('Camera Alert Added'); window.location='{}'</script>'''.format(reverse('forest_officer_view_camera_alerts')))

        except Exception as e:
            print(f"Error saving camera alert: {e}")
            return HttpResponse(f'''<script> alert('Error adding camera alert: {e}'); window.history.back();</script>''')

    else:
        # Handle GET request if needed (should probably just redirect to add form)
        return redirect(reverse('forest_officer_add_camera_alerts'))



def get_camera_alert_details_json(request, alert_id):
    if not request.session.get('is_authenticated'):
        return JsonResponse({'error': 'Authentication required. Please log in.'}, status=403)

    if request.session.get('user_type') != 'officer':
        return JsonResponse({'error': 'Permission denied. Officer access required.'}, status=403)

    try:
        login_id = request.session.get('user_id')
        if not login_id:
            return JsonResponse({'error': 'User session invalid. User ID not found.'}, status=403)

        officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=login_id)
        officer_station = officer.STATION
        if not officer_station:
            return JsonResponse({'error': 'Officer not assigned to a station. Access denied.'}, status=403)

        alert = get_object_or_404(
            camera_alerts.objects.select_related('CAMERA', 'CAMERA__station', 'ANIMAL'),
            pk=alert_id,
            CAMERA__station=officer_station
        )
        
        camera_display_str = "N/A Camera"
        # camera_location_desc_str = "N/A"
        camera_lat_str = "N/A"
        camera_lon_str = "N/A"

        if alert.CAMERA:
            camera_display_str = str(alert.CAMERA) # Uses __str__ from camera model
            camera_id_for_desc = alert.CAMERA.camera_id # Using camera_id field from model
            # location_desc = getattr(alert.CAMERA, 'location_description', 'No specific location description') # If you add this field to camera model
            # camera_location_desc_str = f"Cam ID {camera_id_for_desc} - {location_desc}"
            
            # Explicitly add latitude and longitude
            if alert.CAMERA.latitude is not None: # Check if latitude exists
                camera_lat_str = f"{alert.CAMERA.latitude:.6f}" # Format to 6 decimal places
            if alert.CAMERA.longitude is not None: # Check if longitude exists
                camera_lon_str = f"{alert.CAMERA.longitude:.6f}" # Format to 6 decimal places


        data = {
            'success': True,
            'animal_name': alert.ANIMAL.name if alert.ANIMAL else 'N/A',
            'camera_id_str': camera_display_str,
            # 'camera_location_details': camera_location_desc_str, # This is your descriptive location
            'camera_latitude': camera_lat_str,   # Added latitude
            'camera_longitude': camera_lon_str,  # Added longitude
            'date': alert.date.strftime('%B %d, %Y') if alert.date else 'N/A',
            'time': alert.time.strftime('%I:%M %p') if alert.time else 'N/A',
            'image_url': alert.image.url if alert.image else None,
            'suggested_affected_area': f"Area near {camera_display_str}" if alert.CAMERA else "Specify affected area",
            'suggested_action': f"Caution advised due to sighting of {alert.ANIMAL.name}." if alert.ANIMAL else "General caution advised."
        }
        return JsonResponse(data)
    
    except forest_officer.DoesNotExist:
        return JsonResponse({'success': False, 'error': "Officer profile not found."}, status=404)
    except camera_alerts.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Camera alert not found or access denied.'}, status=404)
    except ObjectDoesNotExist:
        print(f"A related object was not found for alert_id {alert_id}")
        return JsonResponse({'success': False, 'error': 'A related data record was not found.'}, status=404)
    except Exception as e:
        print(f"Error in get_camera_alert_details_json for alert_id {alert_id}: {e}")
        return JsonResponse({'success': False, 'error': 'An internal server error occurred.'}, status=500)


def forest_officer_view_camera_alerts(request):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        # ... (your existing redirect logic) ...
        if request.session.get('user_type') == 'admin':
             return redirect(reverse('login'))
        else:
            return redirect(reverse('login'))

    login_id = request.session.get('user_id')
    if not login_id:
         return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=login_id)
        officer_station = officer.STATION
        if not officer_station: # Ensure officer has a station
            return HttpResponse('''<script> alert('Officer not assigned to a station.'); window.location='{}'</script>'''.format(reverse('forest_officer_home'))) # Or some other appropriate redirect
    except ObjectDoesNotExist:
         return HttpResponse('''<script> alert('Officer profile not found.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
         print(f"Error retrieving officer/station: {e}")
         return HttpResponse('''<script> alert('An error occurred.'); window.history.back();</script>''')

    # Pre-fetch related data for efficiency in the template
    alerts = camera_alerts.objects.filter(
        CAMERA__station=officer_station
    ).select_related(
        'CAMERA',       # For camera_id, lat, lon
        'ANIMAL'        # For animal name, details, image
    ).order_by('-date', '-time') 

    context = {
        'alerts': alerts,
        'officer_station_name': officer_station.name if officer_station else "Your Station" # For page title consistency
    }
    return render(request, 'Forest Officer/View_Camera_Alerts.html', context)

def forest_officer_edit_camera_alerts(request, id): # id is camera_alert.id
    # Authentication and Authorization
    if not request.session.get('is_authenticated'):
        messages.error(request, "Authentication required.")
        return redirect(reverse('login'))
    if request.session.get('user_type') != 'officer':
        messages.error(request, "Access denied. Officer access required.")
        return redirect(reverse('admin_home') if request.session.get('user_type') == 'admin' else reverse('login'))

    login_id = request.session.get('user_id')
    officer_station = None
    try:
        officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=login_id)
        officer_station = officer.STATION
        # It's crucial an officer has a station to correctly filter camera choices for the form
        if not officer_station:
            messages.error(request, "Cannot manage alerts: Your officer profile is not assigned to a station.")
            return redirect(reverse('forest_officer_view_camera_alerts')) # Or officer home
    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found.")
        return redirect(reverse('login'))
    except Exception as e:
        messages.error(request, f"An error occurred fetching your details: {e}")
        print(f"Error fetching officer/station in edit_camera_alerts: {e}")
        return redirect(reverse('forest_officer_view_camera_alerts'))

    # Get the specific camera alert, ensuring it belongs to a camera in the officer's station
    alert_instance = get_object_or_404(camera_alerts.objects.select_related('CAMERA', 'ANIMAL'), id=id, CAMERA__station=officer_station)

    if request.method == 'POST':
        # Pass officer_station for form's internal filtering if needed (e.g., CAMERA choices)
        form = CameraAlertEditForm(request.POST, request.FILES, instance=alert_instance, officer_station=officer_station)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Camera Alert (ID: {alert_instance.id}) updated successfully!")
                return redirect(reverse('forest_officer_view_camera_alerts'))
            except Exception as e:
                print(f"Error saving updated camera alert: {e}")
                messages.error(request, f"Could not update camera alert: {e}")
                form.add_error(None, "An unexpected error occurred while saving.")
        else:
            messages.error(request, "Please correct the errors highlighted below.")
    else: # GET request
        # Pass officer_station for form's __init__ to correctly populate CAMERA choices
        form = CameraAlertEditForm(instance=alert_instance, officer_station=officer_station)

    context = {
        'form': form,
        'alert': alert_instance, # Pass alert_instance for display purposes if needed (e.g., title)
    }
    return render(request, 'Forest Officer/Edit_Camera_Alerts.html', context)



def forest_officer_delete_camera_alerts(request, id):
    # Check authentication and authorization BEFORE fetching the alert
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        if request.session.get('user_type') == 'admin':
             return redirect(reverse('login'))
        else:
            return redirect(reverse('login'))

    # *** Use 'user_id' from session ***
    login_id = request.session.get('user_id')
    if not login_id:
         return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station = officer.STATION
    except ObjectDoesNotExist:
         return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
         print(f"Error retrieving officer/station: {e}")
         return HttpResponse('''<script> alert('An error occurred.'); window.history.back();</script>''')


    # Get the specific camera alert object, ensuring it belongs to the officer's station
    # *** Added CAMERA__station filter here ***
    try:
        alert = get_object_or_404(camera_alerts, id=id, CAMERA__station=officer_station)
    except Exception as e:
         print(f"Error fetching alert for deletion: {e}")
         return HttpResponse('''<script> alert('Could not find alert or you do not have permission to delete it.'); window.history.back();</script>''')

    # You might want to add a confirmation step (e.g., render a delete confirmation template on GET)
    # For simplicity, this assumes deletion happens via POST to this URL

    if request.method == 'POST':
        # If the request is POST, delete the alert
        try:
            alert.delete()
            # Redirect to the view alerts page after successful deletion
            return redirect(reverse('forest_officer_view_camera_alerts'))
        except Exception as e:
            print(f"Error deleting camera alert: {e}")
            return HttpResponse(f'''<script> alert('Error deleting camera alert: {e}'); window.history.back();</script>''')

    else:
        # If it's a GET request to the delete URL, maybe render a confirmation page?
        # Or just redirect back to the list
        return redirect(reverse('forest_officer_view_camera_alerts'))


def forest_officer_bulk_delete_camera_alerts(request):
    # Check authentication and authorization
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        if request.session.get('user_type') == 'admin':
             return redirect(reverse('login'))
        else:
            return redirect(reverse('login'))

    # *** Use 'user_id' from session ***
    login_id = request.session.get('user_id')
    if not login_id:
         return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station = officer.STATION
    except ObjectDoesNotExist:
         return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
         print(f"Error retrieving officer/station: {e}")
         return HttpResponse('''<script> alert('An error occurred.'); window.history.back();</script>''')


    if request.method == 'POST':
        selected_alert_ids = request.POST.getlist('selected_alerts')

        if selected_alert_ids:
            selected_ids = [int(id) for id in selected_alert_ids if id.isdigit()]

            if selected_ids:
                try:
                    # Delete the selected alerts efficiently,
                    # *** ENSURING they belong to the officer's station ***
                    delete_count, _ = camera_alerts.objects.filter(
                        id__in=selected_ids,
                        CAMERA__station=officer_station # Added station filter here
                    ).delete()

                    # Optional: Add a success message
                    # from django.contrib import messages
                    # messages.success(request, f"{delete_count} alerts from your station deleted successfully.")

                except Exception as e:
                     print(f"Error during bulk deletion: {e}")
                     return HttpResponse(f'''<script> alert('Error performing bulk deletion: {e}'); window.history.back();</script>''')

        # Redirect back to the view alerts page after deletion attempt
        return redirect(reverse('forest_officer_view_camera_alerts'))
    else:
        # If it's not a POST request, redirect or return an error
        return redirect(reverse('forest_officer_view_camera_alerts'))



# Custom session check function to avoid repetition
def is_forest_officer(request):
    return request.session.get('is_authenticated') and request.session.get('user_type') == 'officer'

# Helper to redirect based on user type if not officer
def redirect_if_not_officer(request):
    if request.session.get('user_type') == 'admin':
        return redirect(reverse('admin_home'))
    else:
        return redirect(reverse('login')) # Or an 'unauthorized' page


# Existing forest officer views (modified to use the helper functions)

def forest_officer_send_curfew(request):
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    form = CurfewInfoForm()
    return render(request, 'Forest Officer/Send_Curfew_To_Users.html', {'form': form})

# @require_POST # You might consider using this decorator for POST-only views
def forest_officer_send_curfew_post(request):
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    if request.method == 'POST':
        form = CurfewInfoForm(request.POST)
        if form.is_valid():
            curfew = form.save(commit=False)
            user_id = request.session.get('user_id')
            if user_id:
                try:
                    officer = forest_officer.objects.get(LOGIN__id=user_id)
                    curfew.OFFICER = officer
                    curfew.save()
                    return redirect('forest_officer_view_curfew')
                except (forest_officer.DoesNotExist, ObjectDoesNotExist):
                    return render(request, 'Forest Officer/error.html', {'message': 'Could not link curfew to officer.'})
            else:
                 return redirect_if_not_officer(request) # Should not happen if is_forest_officer passes
        else:
            return render(request, 'Forest Officer/Send_Curfew_To_Users.html', {'form': form})
    else:
        return redirect('forest_officer_send_curfew')

def forest_officer_view_curfew(request):
    if not is_forest_officer(request):
        print("DEBUG: User is not authenticated or not an officer.")

        return redirect_if_not_officer(request)
    
    print("DEBUG: User is authenticated as officer.")

    user_id = request.session.get('user_id')
    print(f"DEBUG: User ID from session: {user_id}")

    if user_id:
        try:
            # Get the forest officer instance linked to the user ID from the session
            # Use .filter().first() instead of .get() temporarily for debugging
            # .get() raises an error if not found, .first() returns None
            officer = forest_officer.objects.filter(LOGIN__id=user_id).first()

            if officer:
                print(f"DEBUG: Found Forest Officer: {officer.first_name} {officer.last_name}")
                # Get all curfews associated with this officer
                curfews = curfew_info.objects.filter(OFFICER=officer)
                print(f"DEBUG: Found {curfews.count()} curfews for this officer.")
                return render(request, 'Forest Officer/View_Curfew_To_Users.html', {'curfews': curfews})
            else:
                print(f"DEBUG: No Forest Officer found for login_table ID: {user_id}")
                # Handle the case where no forest officer is linked to the user ID in session
                return render(request, 'Forest Officer/error.html', {'message': 'No forest officer found for this user ID.'})

        except ObjectDoesNotExist:
             # This exception is less likely now with .filter().first(), but kept for safety
             print(f"DEBUG: ObjectDoesNotExist occurred for user ID: {user_id}")
             return render(request, 'error.html', {'message': 'User login information not found.'})
        except Exception as e:
             print(f"DEBUG: An unexpected error occurred in view_curfew: {e}")
             return render(request, 'error.html', {'message': f'An unexpected error occurred: {e}'})
    else:
        print("DEBUG: user_id not found in session.")
        return redirect_if_not_officer(request) # Should not happen if is_forest_officer passes




def forest_officer_edit_curfew(request, curfew_id):
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    curfew = get_object_or_404(curfew_info, id=curfew_id)

    user_id = request.session.get('user_id')
    if user_id:
        try:
            officer = forest_officer.objects.get(LOGIN__id=user_id)
            if curfew.OFFICER != officer:
                return render(request, 'Forest Officer/error.html', {'message': 'You are not authorized to edit this curfew.'}, status=403)
        except (forest_officer.DoesNotExist, ObjectDoesNotExist):
             return render(request, 'Forest Officer/error.html', {'message': 'Could not verify officer for editing.'})
    else:
         return redirect_if_not_officer(request)


    if request.method == 'POST':
        form = CurfewInfoForm(request.POST, instance=curfew)
        if form.is_valid():
            form.save()
            return redirect('forest_officer_view_curfew')
    else:
        form = CurfewInfoForm(instance=curfew)
    return render(request, 'Forest Officer/edit_curfew.html', {'form': form, 'curfew': curfew})


def forest_officer_delete_curfew(request, curfew_id):
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    curfew = get_object_or_404(curfew_info, id=curfew_id)

    user_id = request.session.get('user_id')
    if user_id:
        try:
            officer = forest_officer.objects.get(LOGIN__id=user_id)
            if curfew.OFFICER != officer:
                return render(request, 'error.html', {'message': 'You are not authorized to delete this curfew.'}, status=403)
        except (forest_officer.DoesNotExist, ObjectDoesNotExist):
             return render(request, 'error.html', {'message': 'Could not verify officer for deletion.'})
    else:
         return redirect_if_not_officer(request)


    if request.method == 'POST':
        curfew.delete()
        return redirect('forest_officer_view_curfew')
    return render(request, 'Forest Officer/confirm_delete_curfew.html', {'curfew': curfew})


#Android code api ----------------:

# --- NEW: API View for Regular Users to see Curfew Information ---
# --- MODIFIED: API View for Regular Users to see Curfew Information ---
@api_view(['GET'])
@csrf_exempt
def api_user_view_curfews(request):
    if request.method == 'GET':
        try:
            today = date.today()
            now_time = datetime.now().time() # Get current time for time-based filtering today

            # Define the conditions for a curfew to be considered "active or future"
            # Condition 1: The curfew's end_date is strictly in the future (after today)
            cond1 = Q(end_date__gt=today)

            # Condition 2: The curfew's end_date is today, AND its end_time has not yet passed
            # This covers curfews ending today that are still active or will become active later today
            cond2 = Q(end_date=today, end_time__gte=now_time)

            # Combine conditions using OR:
            # A curfew is included if its end_date is in the future OR it ends today and its end_time hasn't passed.
            active_or_future_curfews = curfew_info.objects.filter(cond1 | cond2).order_by('start_date', 'start_time')

            curfews_data = []
            for curfew in active_or_future_curfews:
                curfews_data.append({
                    'id': curfew.id,
                    'curfew_name': curfew.curfew_name,
                    'curfew_details': curfew.curfew_details,
                    'start_time': curfew.start_time.strftime('%H:%M') if curfew.start_time else "N/A", # Robustness for null times
                    'end_time': curfew.end_time.strftime('%H:%M') if curfew.end_time else "N/A",       # Robustness for null times
                    'start_date': curfew.start_date.isoformat(),
                    'end_date': curfew.end_date.isoformat(),
                    'affected_area': curfew.affected_area,
                    'threat_level': curfew.threat_level,
                    'officer_name': f"{curfew.OFFICER.first_name} {curfew.OFFICER.last_name}" if curfew.OFFICER else "N/A Officer"
                })

            if not curfews_data:
                return JsonResponse({'success': True, 'message': 'No active or future curfews found.', 'curfews': []}, status=200)

            return JsonResponse({'success': True, 'curfews': curfews_data}, status=200)

        except Exception as e:
            print(f"DEBUG: An unexpected error occurred in api_user_view_curfews: {e}")
            return JsonResponse({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)



# Entire views.py code block for User Complaints-----------------------------------:

def forest_officer_view_user_complaints(request):
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    # Assuming 'user_id' in session refers to the ID of the forest_officer's LOGIN instance
    # or the primary key of the forest_officer model itself. Adjust accordingly.
    officer_login_or_pk = request.session.get('user_id') 
    if not officer_login_or_pk:
        messages.error(request, 'Session error: Officer ID not found. Please log in again.')
        return redirect('login') # Or your login URL name

    officer_station = None
    officer_station_name = "No Station Assigned"
    try:
        # Adjust the query based on how 'user_id' relates to 'forest_officer' model.
        # If 'user_id' is the PK of the forest_officer model:
        # officer_profile = forest_officer.objects.select_related('STATION').get(pk=officer_login_or_pk)
        # If 'user_id' is the PK of a related LOGIN model (as suggested by LOGIN_id in original):
        officer_profile = forest_officer.objects.select_related('STATION').get(LOGIN_id=officer_login_or_pk)
        
        if officer_profile.STATION:
            officer_station = officer_profile.STATION
            officer_station_name = officer_station.name
        else:
            # Officer has no station, they will see no complaints specific to a station
            # (unless this logic is changed)
            messages.info(request, "You are not currently assigned to a station. No station-specific complaints to display.")
    except forest_officer.DoesNotExist:
        messages.error(request, 'Officer profile not found. Please contact support.')
        return redirect('forest_officer_home') # Or some other appropriate dashboard/home URL
    except Exception as e: # Catch other potential errors during officer retrieval
        messages.error(request, f'An error occurred while retrieving officer details: {e}')
        return redirect('forest_officer_home')


    # Base queryset for complaints
    all_complaints_qs = complaints.objects.select_related('USER', 'USER__REGULAR_LOGIN', 'STATION')

    if officer_station:
        all_complaints_qs = all_complaints_qs.filter(STATION=officer_station)
    else:
        # If officer has no station, they see no complaints unless you change this logic
        all_complaints_qs = complaints.objects.none() 

    # Initialize filter form with GET data if present (now only contains search_query)
    filter_form = ComplaintFilterForm(request.GET or None)
    search_query = ""

    if filter_form.is_valid():
        search_query = filter_form.cleaned_data.get('search_query', '').strip()

        if search_query:
            # Construct Q objects for searching multiple fields
            # Ensure that related fields (USER__REGULAR_LOGIN__username) are valid
            # and handle potential None values if a complaint might not have a USER or USER.REGULAR_LOGIN
            query_conditions = Q(complaint__icontains=search_query)
            
            # Add user-related searches if USER can exist
            query_conditions |= Q(USER__first_name__icontains=search_query)
            query_conditions |= Q(USER__last_name__icontains=search_query)
            
            # Add username search if USER and REGULAR_LOGIN can exist
            # This assumes USER can be null or USER.REGULAR_LOGIN can be null.
            # If USER and USER.REGULAR_LOGIN are guaranteed, you can simplify.
            # For robustness, you might need to check if request.user.REGULAR_LOGIN exists
            # or handle potential exceptions if related objects are missing.
            # A safer way might involve subqueries or more complex annotations if relations can be sparse.
            query_conditions |= Q(USER__REGULAR_LOGIN__username__icontains=search_query)

            query_conditions |= Q(contact_number__icontains=search_query) # Assumes contact_number is stored as string or can be queried with icontains
            query_conditions |= Q(reply__icontains=search_query)
            
            all_complaints_qs = all_complaints_qs.filter(query_conditions).distinct() 
            # distinct() is important if your Q objects join across tables causing duplicates

    # Always order, even if no search, to ensure consistent presentation
    all_complaints_qs = all_complaints_qs.order_by('-timestamp')

    context = {
        'complaints': all_complaints_qs,
        'officer_station_name': officer_station_name,
        'filter_form': filter_form, 
        'search_query': search_query, 
        # 'start_date_filter' and 'end_date_filter' are removed from context
    }
    return render(request, 'Forest Officer/View_User_Complaints_Forest_officer.html', context)



def forest_officer_send_reply_to_user(request, complaint_id):
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    officer_login_id = request.session.get('user_id')
    if not officer_login_id:
        return render(request, 'error_page.html', {'message': 'Officer login ID not found in session.'}, status=401)

    officer_profile = None
    try:
        officer_login = login_table.objects.get(id=officer_login_id, type='officer')
        officer_profile = forest_officer.objects.get(LOGIN=officer_login)
    except (ObjectDoesNotExist) as e:
        print(f"Error finding officer profile in send_reply: {e}")
        return render(request, 'error_page.html', {'message': 'Officer profile not found.'}, status=404)

    complaint = get_object_or_404(complaints, id=complaint_id)

    # Crucial check - ensure the complaint belongs to *this* officer's station
    if officer_profile.STATION != complaint.STATION:
        return render(request, 'error_page.html', {'message': 'You are not authorized to manage this complaint.'}, status=403)

    if request.method == 'POST':
        form = ComplaintReplyForm(request.POST, instance=complaint)
        if form.is_valid():
            form.save()
            return redirect('forest_officer_view_user_complaints')
    else:
        form = ComplaintReplyForm(instance=complaint)

    return render(request, 'Forest Officer/Reply_To_User_Complaint.html', {'form': form, 'complaint': complaint})


def forest_officer_edit_reply_to_user(request, complaint_id):
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    officer_login_id = request.session.get('user_id')
    if not officer_login_id:
        return render(request, 'error_page.html', {'message': 'Officer login ID not found in session.'}, status=401)

    officer_profile = None
    try:
        officer_login = login_table.objects.get(id=officer_login_id, type='officer')
        officer_profile = forest_officer.objects.get(LOGIN=officer_login)
    except (ObjectDoesNotExist) as e:
        print(f"Error finding officer profile in edit_reply: {e}")
        return render(request, 'error_page.html', {'message': 'Officer profile not found.'}, status=404)

    complaint = get_object_or_404(complaints, id=complaint_id)

    # Crucial check - ensure the complaint belongs to *this* officer's station
    if officer_profile.STATION != complaint.STATION:
        return render(request, 'error_page.html', {'message': 'You are not authorized to manage this complaint.'}, status=403)

    if request.method == 'POST':
        form = ComplaintReplyForm(request.POST, instance=complaint)
        if form.is_valid():
            form.save()
            return redirect('forest_officer_view_user_complaints')
    else:
        form = ComplaintReplyForm(instance=complaint)

    return render(request, 'Forest Officer/Reply_To_User_Complaint.html', {'form': form, 'complaint': complaint, 'editing': True})

@never_cache
def forest_officer_delete_reply_to_user(request, complaint_id):
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    officer_login_id = request.session.get('user_id')
    if not officer_login_id:
        return render(request, 'error_page.html', {'message': 'Officer login ID not found in session.'}, status=401)

    officer_profile = None
    try:
        officer_login = login_table.objects.get(id=officer_login_id, type='officer')
        officer_profile = forest_officer.objects.get(LOGIN=officer_login)
    except (ObjectDoesNotExist) as e:
        print(f"Error finding officer profile in delete_reply: {e}")
        return render(request, 'error_page.html', {'message': 'Officer profile not found.'}, status=404)

    complaint = get_object_or_404(complaints, id=complaint_id)

    # Crucial check - ensure the complaint belongs to *this* officer's station
    if officer_profile.STATION != complaint.STATION:
        return render(request, 'error_page.html', {'message': 'You are not authorized to manage this complaint.'}, status=403)

    if request.method == 'POST':
        complaint.reply = ""
        complaint.save()
        return redirect('forest_officer_view_user_complaints')

    return render(request, 'Forest Officer/Confirm_Delete_Reply.html', {'complaint': complaint})

# --- New Forest Officer Views for Alerts to Users ---

@never_cache
def forest_officer_send_alert_to_user(request):
    # Check if user is authenticated and is an officer
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)
    
    user_id = request.session.get('user_id')
    officer = None
    officer_station_instance = None # Use a more descriptive name

    if user_id:
        try:
            # Ensure related station is fetched efficiently if not already loaded
            # select_related can help if STATION is frequently accessed after fetching officer
            officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=user_id)
            officer_station_instance = officer.STATION
        except forest_officer.DoesNotExist:
            return render(request, 'error.html', {'message': 'Officer profile not found. Cannot determine station.'})
        except forest_officer.STATION.RelatedObjectDoesNotExist: # Or just forest_station.DoesNotExist if STATION can be null
             return render(request, 'error.html', {'message': 'Officer is not assigned to a station.'})
    else:
        # This case should ideally be caught by is_forest_officer
        return redirect_if_not_officer(request)

    if request.method == 'POST':
        form = AlertToUserForm(request.POST, officer_station=officer_station_instance)
        if form.is_valid():
            alert = form.save(commit=False)
            # Link the alert to the logged-in forest officer
            
            alert.OFFICER = officer

            # --- Set target_station based on target_audience ---
            if alert.target_audience == 'OWN_STATION':
                # officer_station_instance will be the officer's assigned station
                # This is guaranteed if officer.STATION is non-nullable.
                alert.target_station = officer_station_instance
            elif alert.target_audience == 'ALL':
                alert.target_station = None
            # ----------------------------------------------------


            # ---- Populate camera latitude and longitude ----
            selected_camera_alert = form.cleaned_data['CAMERA_ALERT'] # Field is required
            if selected_camera_alert and selected_camera_alert.CAMERA:
                alert.camera_latitude = selected_camera_alert.CAMERA.latitude
                alert.camera_longitude = selected_camera_alert.CAMERA.longitude
            # ---------------------------------------------

            alert.save()
            return redirect('forest_officer_view_alert_to_user') # Ensure this URL name is correct

        else:
            # Re-pass officer_station if form is invalid and re-rendered on POST
            return render(request, 'Forest Officer/Send_Alert_to_User_by_Officer.html', {'form': form})
    else: # GET request
        # Pass the officer's station to the form
        form = AlertToUserForm(officer_station=officer_station_instance)
        return render(request, 'Forest Officer/Send_Alert_to_User_by_Officer.html', {'form': form})

@never_cache
def forest_officer_view_alert_to_user(request):
    # Check if user is authenticated and is an officer
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    # Get alerts created by the logged-in forest officer
    user_id = request.session.get('user_id')
    if user_id:
        try:
            officer = forest_officer.objects.get(LOGIN__id=user_id)
            alerts = alert_to_user.objects.filter(OFFICER=officer)
            return render(request, 'Forest Officer/View_Alert_to_User.html', {'alerts': alerts})
        except (forest_officer.DoesNotExist, ObjectDoesNotExist):
            return render(request, 'error.html', {'message': 'Could not retrieve officer or alerts.'})
    else:
        return redirect_if_not_officer(request) # Should not happen if is_forest_officer passes


@never_cache
def forest_officer_edit_alert_to_user(request, alert_id):
    # 1. Check if user is authenticated via session
    if not request.session.get('is_authenticated'):
        # If not authenticated at all, redirect to login
        # messages.error(request, "You must be logged in to view this page.") # Optional
        return redirect(reverse('login')) # Assuming 'login' is the name of your login URL

    # 2. Check if the authenticated user is an officer
    if request.session.get('user_type') != 'officer':
        # If authenticated but not an officer (e.g., admin), they shouldn't edit officer-specific alerts
        # messages.error(request, "Access Denied: This page is for forest officers only.") # Optional
        if request.session.get('user_type') == 'admin': # Example: redirect admin to their home
             return redirect(reverse('admin_home')) # Or a generic access denied page
        else: # Other unknown types
             return redirect(reverse('login'))


    # Get the specific alert to be edited or return 404
    alert_instance = get_object_or_404(alert_to_user.objects.select_related('OFFICER', 'OFFICER__STATION'), id=alert_id)

    # Get the logged-in officer and their station (needed for the form and authorization)
    login_id = request.session.get('user_id') # We know this exists if user_type is 'officer'
                                         # because the above checks would have caught it otherwise.
    try:
        # Fetch the officer who is currently logged in
        current_officer = forest_officer.objects.select_related('STATION').get(LOGIN__id=login_id)
        officer_station_for_form = current_officer.STATION

        # Authorization check: Ensure the logged-in officer is the one who created the alert
        if alert_instance.OFFICER != current_officer:
            # messages.error(request, "Authorization Denied: You can only edit alerts you created.") # Optional
            # Consider a specific 'access_denied.html' template or redirect to a safe page
            return render(request, 'error.html', {'message': 'You are not authorized to edit this alert as you did not create it.'}, status=403)

        if not officer_station_for_form: # Check if the editing officer has a station assigned
            # messages.error(request, "Cannot populate camera alerts: Your officer profile is not assigned to a station.") # Optional
            # Decide how to handle this: maybe allow editing but camera alerts will be empty, or deny editing.
            # For now, we proceed, and the form's __init__ will handle officer_station being None for CAMERA_ALERT.
            pass


    except forest_officer.DoesNotExist:
        # messages.error(request, "Your officer profile could not be found. Please log in again.") # Optional
        return render(request, 'error.html', {'message': 'Your officer profile could not be found. Please try logging in again.'})
    except ObjectDoesNotExist: # Catch other potential missing related objects
        # messages.error(request, "A critical data record related to your profile is missing.") # Optional
        return render(request, 'error.html', {'message': 'Could not verify officer details for editing alert due to missing related data.'})


    if request.method == 'POST':
        form = AlertToUserForm(request.POST, instance=alert_instance, officer_station=officer_station_for_form)
        if form.is_valid():
            form.save()
            # messages.success(request, "Alert updated successfully!") # Optional
            return redirect('forest_officer_view_alert_to_user')
        # else:
            # messages.error(request, "Please correct the errors highlighted below.") # Optional
    else: # GET request
        form = AlertToUserForm(instance=alert_instance, officer_station=officer_station_for_form)

    return render(request, 'Forest Officer/Edit_Alert_to_User.html', {'form': form, 'alert': alert_instance})

@never_cache
def forest_officer_delete_alert_to_user(request, alert_id):
    # Check if user is authenticated and is an officer
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    # Get the specific alert or return 404
    alert = get_object_or_404(alert_to_user, id=alert_id)

    # Ensure the logged-in officer is the one who created the alert (authorization check)
    user_id = request.session.get('user_id')
    if user_id:
        try:
            officer = forest_officer.objects.get(LOGIN__id=user_id)
            if alert.OFFICER != officer:
                return render(request, 'error.html', {'message': 'You are not authorized to delete this alert.'}, status=403)
        except (forest_officer.DoesNotExist, ObjectDoesNotExist):
             return render(request, 'error.html', {'message': 'Could not verify officer for deleting alert.'})
    else:
         return redirect_if_not_officer(request)

    if request.method == 'POST':
        alert.delete()
        # Redirect back to the view alerts page
        return redirect('forest_officer_view_alert_to_user')

    # For GET request, show a confirmation page
    return render(request, 'Forest Officer/Confirm_Delete_Alert.html', {'alert': alert})


def forest_officer_view_notification(request):

    # Check if user is authenticated and is an officer
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        if request.session.get('user_type') == 'admin':
            return redirect(reverse('admin_home'))
        else:
            return redirect(reverse('login'))

    # If checks pass, get the officer and filter cameras
    # *** CORRECTED: Use 'user_id' from session ***
    login_id = request.session.get('user_id')
    if not login_id:
         return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        # Find the officer linked to the login session
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station = officer.STATION # Get the station associated with the officer
    except ObjectDoesNotExist:
         return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
         print(f"Error retrieving officer/station: {e}")
         return HttpResponse('''<script> alert('An error occurred.'); window.history.back();</script>''')


    # Fetch all notification objects from the database
    all_notifications = admin_notification.objects.all()

    # Create a context dictionary to pass data to the template
    context = {'all_notifications': all_notifications}

    # Render the template with the notifications data
    return render(request, 'Forest Officer/View_Notification.html', context)


#views.py code for Send Report to Admin:--------------------------------------------

def forest_officer_send_daily_report(request):
    """
    View to display the form for Forest Officer to send a daily report.
    """
    # Check if user is authenticated and is an officer
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        # Redirect non-officers (including admins based on your pattern) to login
        return redirect(reverse('login'))

    # Get the logged-in officer's details
    login_id = request.session.get('user_id')
    if not login_id:
        return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        # Ensure the officer profile exists for the logged-in login_table user
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        # We don't strictly need the officer object itself for *rendering* the form,
        # but retrieving it here ensures the user has a valid officer profile
        # before they even see the form.
    except ObjectDoesNotExist:
        return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
        print(f"Error retrieving officer: {e}")
        return HttpResponse('''<script> alert('An error occurred finding officer profile.'); window.history.back();</script>''')

    # Render the form template
    # No specific data from the DB is needed to render this simple form
    return render(request, 'Forest Officer/Send_Daily_Report.html', {})


def forest_officer_send_daily_report_post(request):
    """
    View to handle the submission of the daily report form.
    """
    # Check if user is authenticated and is an officer
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        # Redirect non-officers (including admins) to login
        return redirect(reverse('login'))

    # Get the logged-in officer's details
    login_id = request.session.get('user_id')
    if not login_id:
        return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        # Retrieve the officer object to link the report to them
        officer = forest_officer.objects.get(LOGIN__id=login_id)
    except ObjectDoesNotExist:
        return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
        print(f"Error retrieving officer: {e}")
        return HttpResponse('''<script> alert('An error occurred finding officer profile.'); window.history.back();</script>''')

    if request.method == 'POST':
        # Get data from the POST request
        report_file = request.FILES.get('report_file') # Assuming name='report_file' for file input
        report_date_str = request.POST.get('report_date') # Assuming name='report_date' for date input

        # --- Basic Validation ---
        if not report_file:
            return HttpResponse('''<script> alert('Report file is required.'); window.history.back();</script>''')

        if not report_date_str:
             return HttpResponse('''<script> alert('Report date is required.'); window.history.back();</script>''')

        # Convert date string to Python date object
        try:
            # Assuming date format is 'YYYY-MM-DD' from HTML date input
            report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
        except ValueError:
            return HttpResponse('''<script> alert('Invalid date format.'); window.history.back();</script>''')
        # ------------------------

        # --- Create and Save Daily Report Object ---
        try:
            daily_report_obj = daily_reports.objects.create(
                OFFICER=officer,          # Link to the logged-in officer
                report=report_file,       # Save the uploaded file
                date=report_date          # Save the report date
            )
            # No need to explicitly call daily_report_obj.save() after create()

            # Success message and redirect
            return HttpResponse('''<script> alert('Daily Report Submitted Successfully!'); window.location='{}'</script>'''.format(reverse('forest_officer_view_daily_reports'))) # Redirect to a view showing reports

        except Exception as e:
            # Handle potential errors during saving (e.g., database issues)
            print(f"Error saving daily report: {e}")
            return HttpResponse(f'''<script> alert('Error submitting daily report: {e}'); window.history.back();</script>''')

    else:
        # If not a POST request, redirect to the form page
        return redirect(reverse('forest_officer_send_daily_report'))



# --- Forest Officer Functions ---

def forest_officer_request_tech_support(request):
    """
    View for Forest Officers to request tech support.
    Displays a form to specify the issue and description.
    Also displays the station's phone number.
    """
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        return redirect(reverse('login'))

    login_id = request.session.get('user_id')
    if not login_id:
        return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        station_phone = officer.STATION.phone
    except ObjectDoesNotExist:
        return HttpResponse('''<script> alert('Officer or Station profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
        print(f"Error retrieving officer/station for tech support request: {e}")
        return HttpResponse('''<script> alert('An error occurred. Please try again.'); window.history.back();</script>''')

    if request.method == 'POST':
        issue_type = request.POST.get('issue_type')
        description = request.POST.get('description')

        if not issue_type or not description:
            return HttpResponse('''<script> alert('Please select an issue type and provide a description.'); window.history.back();</script>''')

        try:
            TechSupportRequest.objects.create(
                OFFICER=officer,
                issue_type=issue_type,
                description=description,
                status='pending' # Default status
            )
            return HttpResponse('''<script> alert('Tech Support Request submitted successfully!'); window.location='{}'</script>'''.format(reverse('forest_officer_view_tech_support_requests'))) # Redirect to a view showing their requests
        except Exception as e:
            print(f"Error saving tech support request: {e}")
            return HttpResponse(f'''<script> alert('Error submitting request: {e}'); window.history.back();</script>''')

    context = {
        'station_phone': station_phone,
    }
    return render(request, 'Forest Officer/request_tech_support.html', context)


def forest_officer_view_tech_support_requests(request):
    """
    View for Forest Officers to see their submitted tech support requests.
    """
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        return redirect(reverse('login'))

    login_id = request.session.get('user_id')
    if not login_id:
        return HttpResponse('''<script> alert('Session error: User ID not found.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        requests = TechSupportRequest.objects.filter(OFFICER=officer).order_by('-request_date')
    except ObjectDoesNotExist:
        return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
        print(f"Error retrieving officer tech support requests: {e}")
        return HttpResponse('''<script> alert('An error occurred. Please try again.'); window.history.back();</script>''')

    context = {
        'requests': requests,
    }
    return render(request, 'Forest Officer/view_tech_support_requests.html', context)


# --- Admin Functions ---

def admin_view_tech_support_requests(request):
    """
    View for Admins to see all tech support requests, with search and filter capabilities.
    """
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        return redirect(reverse('login'))

    # Start with all requests, ordered by request date (newest first)
    requests_query = TechSupportRequest.objects.all().order_by('-request_date')

    # --- Search Logic ---
    search_officer = request.GET.get('search_officer', '').strip()
    if search_officer:
        # Split the search term into keywords (e.g., "John Doe" -> ["John", "Doe"])
        keywords = search_officer.split()
        officer_search_filters = Q()

        for keyword in keywords:
            # For each keyword, search in first_name, last_name of the OFFICER,
            # or in the name of their associated forest_station (if applicable).
            # We combine these with OR for each keyword.
            keyword_q = Q()
            # Search in Officer's first name
            keyword_q |= Q(OFFICER__first_name__icontains=keyword)
            # Search in Officer's last name
            keyword_q |= Q(OFFICER__last_name__icontains=keyword)
            # Assuming forest_officer model has a ForeignKey to a ForestStation model
            # and that ForestStation has a 'name' field. Adjust 'OFFICER__station__name' as needed.
            # You might need to adjust this depending on your forest_officer model's structure.
            # Example: if Officer has a 'station' field which links to a ForestStation model.
            if hasattr(TechSupportRequest.OFFICER.field.related_model, 'station'):
                 keyword_q |= Q(OFFICER__station__name__icontains=keyword)

            # Combine individual keyword Q objects with AND for multi-word searches
            # This means ALL keywords must be found somewhere in the officer's name/station.
            officer_search_filters &= keyword_q if officer_search_filters else keyword_q

        # Apply the combined officer search filters to the query
        requests_query = requests_query.filter(officer_search_filters)

    # --- Status Filter Logic ---
    status_filter = request.GET.get('status_filter', '')
    if status_filter:
        requests_query = requests_query.filter(status=status_filter)

    try:
        # Execute the final query
        requests = requests_query.distinct() # Use distinct to prevent duplicates if multiple Q matches
    except Exception as e:
        print(f"Error retrieving tech support requests: {e}")
        return HttpResponse('''<script> alert('An error occurred while fetching requests. Please try again.'); window.history.back();</script>''')

    context = {
        'requests': requests,
        'search_officer': search_officer, # Pass back to pre-fill search input
        'status_filter': status_filter,   # Pass back to pre-select filter option
    }
    return render(request, 'Admin/manage_tech_support_requests.html', context)




def admin_update_tech_support_status(request, request_id):
    """
    View for Admins to update the status of a tech support request.
    """
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'admin':
        return redirect(reverse('login'))

    try:
        tech_request = TechSupportRequest.objects.get(id=request_id)
    except ObjectDoesNotExist:
        return HttpResponse('''<script> alert('Tech Support Request not found.'); window.history.back();</script>''')
    except Exception as e:
        print(f"Error retrieving tech support request for update: {e}")
        return HttpResponse('''<script> alert('An error occurred. Please try again.'); window.history.back();</script>''')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        resolution_notes = request.POST.get('resolution_notes')

        if new_status and new_status in [choice[0] for choice in TechSupportRequest.status.field.choices]:
            tech_request.status = new_status
            if new_status == 'resolved':
                tech_request.resolved_date = datetime.now()
                tech_request.resolution_notes = resolution_notes # Save resolution notes if resolved
            else:
                tech_request.resolution_notes = None # Clear notes if status changes from resolved
                tech_request.resolved_date = None
            tech_request.save()
            return HttpResponse('''<script> alert('Tech Support Request status updated successfully!'); window.location='{}'</script>'''.format(reverse('admin_view_tech_support_requests')))
        else:
            return HttpResponse('''<script> alert('Invalid status provided.'); window.history.back();</script>''')

    context = {
        'tech_request': tech_request,
        'statuses': TechSupportRequest.status.field.choices # Pass choices for the dropdown
    }
    return render(request, 'Admin/update_tech_support_status.html', context)







# --- API Endpoints for Android App ---

# API for WorkManager Polling (Get NEW alerts)
@csrf_exempt # Consider proper authentication for production
def api_get_new_alerts(request):
    print("--- DEBUG: >>> Entered api_get_new_alerts view <<< ---")

    if request.method == 'POST':
        print("--- DEBUG: Inside POST method check in api_get_new_alerts ---")
        try:
            print("--- DEBUG: Attempting to parse JSON body in api_get_new_alerts ---")
            data = json.loads(request.body)
            print(f"--- DEBUG: Successfully parsed JSON body: {data} ---")

            user_login_id = data.get('user_login_id')
            last_alert_id = data.get('last_alert_id', 0) # For general alerts

            if user_login_id is None:
                print("--- DEBUG: user_login_id is None in api_get_new_alerts ---")
                return JsonResponse({'error': 'user_login_id is required'}, status=400)

            user_station = None
            try:
                print("--- Debug: Attempting to get user_table object using REGULAR_LOGIN__id in api_get_new_alerts ---")
                user = user_table.objects.get(REGULAR_LOGIN__id=user_login_id)
                print(f"--- Debug: Found user_table object for REGULAR_LOGIN__id: {user_login_id} (user_table id: {user.id}) ---")
                user_station = user.STATION # This can be None if user is not assigned to a station
                if user_station:
                    print(f"--- Debug: User station: {user_station.name} (ID: {user_station.id}) ---")
                else:
                    print(f"--- Debug: User {user.id} is not assigned to any station. ---")
            except user_table.DoesNotExist:
                print(f"--- Debug: User not found in user_table for REGULAR_LOGIN__id: {user_login_id} ---")
                return JsonResponse({'error': 'User profile not found for provided login ID'}, status=404)
            except Exception as e:
                print(f"--- Debug: Error fetching user_table profile by REGULAR_LOGIN__id: {e} ---")
                return JsonResponse({'error': 'Internal server error fetching user profile'}, status=500)

            # 1. Fetch general alerts (existing logic)
            print("--- Debug: Querying for new general alerts in api_get_new_alerts ---")
            general_alerts_query_base = alert_to_user.objects.all() # Start with all

            # Apply audience filtering
            audience_filter = models.Q(target_audience='ALL')
            if user_station:
                audience_filter |= models.Q(target_audience='OWN_STATION', target_station=user_station)
            general_alerts_query_filtered_audience = general_alerts_query_base.filter(audience_filter)

            if last_alert_id == 0: # Special handling for the very first poll
                print(f"--- Debug: last_alert_id is 0. Fetching only the most recent general alert(s). ---")
                # Option A: Fetch only the single most recent alert
                # most_recent_alert = general_alerts_query_filtered_audience.order_by('-id').first()
                # if most_recent_alert:
                #     new_general_alerts = alert_to_user.objects.filter(id=most_recent_alert.id) # Queryset of one
                # else:
                #     new_general_alerts = alert_to_user.objects.none() # Empty queryset

                # Option B: Fetch alerts from the last N hours (e.g., 24 hours)
                # from django.utils import timezone
                # from datetime import timedelta
                time_threshold = timezone.now() - timedelta(hours=24)
                new_general_alerts = general_alerts_query_filtered_audience.filter(
                    created_at__gte=time_threshold
                ).order_by('id')
                print(f"--- Debug: Fetched {new_general_alerts.count()} general alerts from last 24 hours due to last_alert_id=0 ---")

            else: # Normal polling behavior
                print(f"--- Debug: last_alert_id is {last_alert_id}. Fetching general alerts with id > {last_alert_id}. ---")
                new_general_alerts = general_alerts_query_filtered_audience.filter(
                    id__gt=last_alert_id
                ).order_by('id')

            print(f"--- Debug: Found {new_general_alerts.count()} new general alerts ---")

            alerts_data = []
            print("--- Debug: Starting loop to process new general alerts ---")
            for i, alert in enumerate(new_general_alerts):
                # (Your existing serialization logic for general alerts)
                print(f"--- Debug: Processing general alert {i+1}/{new_general_alerts.count()} with ID: {alert.id} ---")
                try:
                    alert_dict = model_to_dict(alert, fields=[
                        'id', 'affected_area', 'threat_level', 'action_to_take'
                    ])
    # Manually add created_at (it will be a datetime object initially)
    # JsonResponse will later serialize it to an ISO 8601 string.
                    alert_dict['created_at'] = alert.created_at 

                    print(f"--- Debug: model_to_dict output (plus manual created_at) for alert ID {alert.id}: {alert_dict} ---")                  
                    alert_dict['type'] = 'general' # Add type for client differentiation

                    if alert.CAMERA_ALERT:
                        # ... (your camera alert details logic) ...
                        camera_alert_details = {
                            'camera_id': alert.CAMERA_ALERT.CAMERA.id if alert.CAMERA_ALERT.CAMERA else None,
                            'animal_name': alert.CAMERA_ALERT.ANIMAL.name if alert.CAMERA_ALERT.ANIMAL else None,
                            'date': alert.CAMERA_ALERT.date.isoformat() if alert.CAMERA_ALERT.date else None,
                            'time': alert.CAMERA_ALERT.time.strftime('%H:%M:%S') if alert.CAMERA_ALERT.time else None,
                            'image_url': request.build_absolute_uri(alert.CAMERA_ALERT.image.url) if alert.CAMERA_ALERT.image else None,
                        }
                        alert_dict['camera_alert_details'] = camera_alert_details
                    else:
                        alert_dict['camera_alert_details'] = {}
                    alerts_data.append(alert_dict)
                except Exception as e:
                    print(f"--- Debug: ERROR during serialization of general alert ID {alert.id}: {e} ---")
                    continue
            print("--- Debug: Finished loop processing new general alerts ---")


            # 2. Fetch Curfew Alerts
            curfew_alerts_data = []
            if user_station: # Only fetch curfew alerts if the user is associated with a station
                print(f"--- Debug: User is associated with station {user_station.id}. Fetching curfew alerts. ---")
                now = timezone.now()
                in_24_hours = now + timedelta(hours=24)
                
                # Get curfews created by officers from the same station as the user
                potential_curfews = curfew_info.objects.filter(OFFICER__STATION=user_station)
                print(f"--- Debug: Found {potential_curfews.count()} potential curfews for station {user_station.id}. ---")

                for curfew in potential_curfews:
                    try:
                        # Combine date and time to create aware datetime objects
                        # Assumes start_date and start_time are naive and represent time in Django's default timezone
                        naive_start_datetime = datetime.combine(curfew.start_date, curfew.start_time)
                        curfew_start_datetime_aware = timezone.make_aware(naive_start_datetime, timezone.get_default_timezone())
                        
                        naive_end_datetime = datetime.combine(curfew.end_date, curfew.end_time)
                        curfew_end_datetime_aware = timezone.make_aware(naive_end_datetime, timezone.get_default_timezone())

                        # Check if curfew starts within the next 24 hours and has not already passed
                        if now <= curfew_start_datetime_aware < in_24_hours:
                            print(f"--- Debug: Curfew ID {curfew.id} ('{curfew.curfew_name}') is upcoming. Adding to list. ---")
                            curfew_dict = {
                                'id': curfew.id, # Curfew ID
                                'type': 'curfew', # Explicitly type it
                                'curfew_name': curfew.curfew_name,
                                'details': curfew.curfew_details,
                                'affected_area': curfew.affected_area,
                                'threat_level': curfew.threat_level,
                                'start_datetime': curfew_start_datetime_aware.isoformat(),
                                'end_datetime': curfew_end_datetime_aware.isoformat(),
                                'action_to_take': (
                                    f"Curfew '{curfew.curfew_name}' in effect for {curfew.affected_area}. "
                                    f"Starts: {curfew.start_date.strftime('%Y-%m-%d')} {curfew.start_time.strftime('%H:%M')}. "
                                    f"Ends: {curfew.end_date.strftime('%Y-%m-%d')} {curfew.end_time.strftime('%H:%M')}."
                                )
                            }
                            curfew_alerts_data.append(curfew_dict)
                        else:
                            print(f"--- Debug: Curfew ID {curfew.id} ('{curfew.curfew_name}') is not within the 24-hour window or has passed. Start: {curfew_start_datetime_aware}. Now: {now} ---")
                    except Exception as e:
                        print(f"--- Debug: ERROR processing curfew ID {curfew.id}: {e} ---")
                        continue # Skip this curfew on error
            else:
                print("--- Debug: User not associated with a station or user_station is None. Skipping curfew alerts. ---")

            print(f"--- Debug: Final general alerts_data list size: {len(alerts_data)} ---")
            print(f"--- Debug: Final curfew_alerts_data list size: {len(curfew_alerts_data)} ---")
            
            print("--- Debug: Returning successful JSON response from api_get_new_alerts ---")
            return JsonResponse({'alerts': alerts_data, 'curfew_alerts': curfew_alerts_data})

        except json.JSONDecodeError:
            print("--- DEBUG: JSONDecodeError caught in api_get_new_alerts ---")
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"--- Debug: An unexpected error occurred in api_get_new_alerts POST block: {e} ---")
            # For security, in production, you might want to log 'e' but return a generic error message
            return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'}, status=500)

    else:
        print("--- DEBUG: Received non-POST request in api_get_new_alerts ---")
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
@csrf_exempt # Again, consider proper authentication
def api_get_all_user_alerts(request):
     if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Android app should send its user's RegularUserLogin ID
            user_login_id = data.get('user_login_id')

            if user_login_id is None:
                 return JsonResponse({'error': 'user_login_id is required'}, status=400)

            # Get the user's associated station
            try:
                user = user_table.objects.get(REGULAR_LOGIN__id=user_login_id)
                user_station = user.STATION # This could be None
            except user_table.DoesNotExist:
                return JsonResponse({'error': 'User not found'}, status=404)

            # Query for ALL relevant alerts for this user with select_related
            all_alerts = alert_to_user.objects.select_related(
                'CAMERA_ALERT__ANIMAL',
                'CAMERA_ALERT__CAMERA',
                'OFFICER__STATION',
                'target_station'
            ).filter(
                 # Use Q objects for OR conditions
                models.Q(target_audience='ALL') |
                models.Q(target_audience='OWN_STATION', target_station=user_station)
            ).order_by('-created_at') # Order by latest first

            alerts_data = []
            for alert in all_alerts:
                # Basic serialization. Include relevant camera_alert info.
                alert_dict = model_to_dict(alert, fields=[
                    'id', 'affected_area', 'threat_level', 'action_to_take', 'created_at'
                ])
                # Add camera alert details
                if alert.CAMERA_ALERT:
                     camera_alert_details = {
                        'camera_id': alert.CAMERA_ALERT.CAMERA.id if alert.CAMERA_ALERT.CAMERA else None,
                        'animal_name': alert.CAMERA_ALERT.ANIMAL.name if alert.CAMERA_ALERT.ANIMAL else None,
                        'date': alert.CAMERA_ALERT.date.isoformat() if alert.CAMERA_ALERT.date else None,
                        'time': alert.CAMERA_ALERT.time.strftime('%H:%M:%S') if alert.CAMERA_ALERT.time else None,
                         'image_url': request.build_absolute_uri(alert.CAMERA_ALERT.image.url) if alert.CAMERA_ALERT.image else None,
                     }
                     alert_dict['camera_alert_details'] = camera_alert_details

                alerts_data.append(alert_dict)

            return JsonResponse({'alerts': alerts_data})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            # Log the error in a real application
            return JsonResponse({'error': str(e)}, status=500)

     return JsonResponse({'error': 'Only POST method allowed'}, status=405)
















# --- User Report Views -------------------------------------

# ## Android-------------------------####
@csrf_exempt # Allow POST requests without CSRF token for simplicity in development
def report_sighting_api(request):
    print("--- Debug: Entered report_sighting_api view ---")

    if request.method == 'POST':
        print("--- Debug: Received POST request for report_sighting ---")

        try:
            # Django automatically parses multipart form data into request.POST and request.FILES
            data = request.POST # Text fields are in request.POST
            uploaded_image = request.FILES.get('image') # File fields are in request.FILES

            print(f"--- Debug: Accessed data from request.POST: {data} ---")
            print(f"--- Debug: Accessed uploaded image from request.FILES: {uploaded_image} ---")

            # Get data from the request using the correct keys from Android
            user_id_str = data.get('user_id') # Android sends user_id (which is the RegularUserLogin ID)
            animal_name = data.get('animal') # Android sends animal
            animal_type = data.get('animal_type') # Android sends animal_type
            location_details = data.get('location_details') # Android sends location_details
            date_str = data.get('date') # Android sends date
            time_str = data.get('time') # Android sends time
            latitude_str = data.get('latitude') # Android sends latitude
            longitude_str = data.get('longitude') # Android sends longitude
            station_id_str = data.get('station_id') # Android sends station_id


            print(f"--- Debug: Received data - user_id: {user_id_str}, animal: {animal_name}, animal_type: {animal_type}, location_details: {location_details}, date: {date_str}, time: {time_str}, latitude: {latitude_str}, longitude: {longitude_str}, station_id: {station_id_str} ---")


            # --- Validation ---
            if not user_id_str or not animal_name or not animal_type or not location_details or not date_str or not time_str:
                 print("--- Debug: Missing required fields ---")
                 missing_fields = []
                 if not user_id_str: missing_fields.append('user_id')
                 if not animal_name: missing_fields.append('animal')
                 if not animal_type: missing_fields.append('animal_type')
                 if not location_details: missing_fields.append('location_details')
                 if not date_str: missing_fields.append('date')
                 if not time_str: missing_fields.append('time')
                 return JsonResponse({'success': False, 'message': f'Missing required fields: {", ".join(missing_fields)}'}, status=400)

            try:
                # Convert user_id_str to int (this is the RegularUserLogin ID)
                regular_user_login_id = int(user_id_str)
            except ValueError:
                print(f"--- Debug: Invalid user_id format: {user_id_str} ---")
                return JsonResponse({'success': False, 'message': 'Invalid User ID format'}, status=400)

            # Validate and convert date and time strings
            try:
                sighting_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                print(f"--- Debug: Invalid date format: {date_str} ---")
                return JsonResponse({'success': False, 'message': 'Invalid date format. Use %Y-%m-%d'}, status=400)

            try:
                sighting_time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                print(f"--- Debug: Invalid time format: {time_str} ---")
                return JsonResponse({'success': False, 'message': 'Invalid time format. Use HH:MM (24hr)'}, status=400)

            # Validate and convert latitude and longitude (optional fields)
            latitude = None
            if latitude_str:
                try:
                    latitude = float(latitude_str)
                except ValueError:
                    print(f"--- Debug: Invalid latitude format: {latitude_str} ---")
                    return JsonResponse({'success': False, 'message': 'Invalid latitude format'}, status=400)

            longitude = None
            if longitude_str:
                try:
                    longitude = float(longitude_str)
                except ValueError:
                    print(f"--- Debug: Invalid longitude format: {longitude_str} ---")
                    return JsonResponse({'success': False, 'message': 'Invalid longitude format'}, status=400)

            # Validate and get the ForestStation object (optional field)
            station = None
            if station_id_str:
                try:
                    station_id = int(station_id_str)
                    print(f"--- Debug: Parsed station_id: {station_id} ---")
                    try:
                        station = forest_station.objects.get(id=station_id)
                        print(f"--- Debug: Found ForestStation: {station.name} ---")
                    except forest_station.DoesNotExist:
                        print(f"--- Debug: ForestStation with ID {station_id} does not exist ---")
                        # You might return an error here or allow saving with station=None
                        # For now, we'll allow saving with station=None if ID is invalid
                        station = None
                        print("--- Debug: Setting station to None due to invalid ID ---")

                except ValueError:
                    print(f"--- Debug: Invalid station_id format: {station_id_str} ---")
                    # Allow saving with station=None if format is invalid
                    station = None
                    print("--- Debug: Setting station to None due to invalid format ---")

            # --- End Validation ---


            # Find the user based on RegularUserLogin ID
            try:
                # Find user_table based on REGULAR_LOGIN__id
                user = user_table.objects.get(REGULAR_LOGIN__id=regular_user_login_id) # Use the correct variable name and lookup
                # Avoid accessing user.name directly
                print(f"--- Debug: Found user_table for RegularUserLogin ID {regular_user_login_id} (user_table id: {user.id}) ---")
            except user_table.DoesNotExist:
                print(f"--- Debug: User profile not found for RegularUserLogin ID {regular_user_login_id} ---")
                return JsonResponse({'success': False, 'message': 'User profile not found'}, status=404)
            except Exception as e:
                 print(f"--- Debug: Error fetching user_table profile by RegularUserLogin ID: {e} ---")
                 return JsonResponse({'success': False, 'message': 'Internal server error fetching user profile'}, status=500)


            # Handle the uploaded image file (uploaded_image is already obtained from request.FILES)
            print(f"--- Debug: Received uploaded image: {uploaded_image} ---")


            # Create a new user_upload instance (using the correct model name)
            # --- CORRECTED: Use user_upload instead of UserReport ---
            sighting = user_upload(
                USER=user, # Link to the user_table instance
                animal=animal_name,
                animal_type=animal_type, 
                location_details=location_details,
                date=sighting_date,
                time=sighting_time,
            
                latitude=latitude, 
                longitude=longitude, 
                station=station, 
                image=uploaded_image # Save the uploaded image file
            )
            # Save the user_upload instance
            sighting.save()
            print(f"--- Debug: user_upload saved successfully with ID: {sighting.id} ---")


            return JsonResponse({'success': True, 'message': 'Sighting reported successfully!', 'report_id': sighting.id}) # Optionally return the report ID

        except Exception as e:
            # Catch any other unexpected errors during the process
            print(f"--- Debug: An unexpected error occurred during report_sighting: {e} ---")
            # Return a generic 500 error response
            return JsonResponse({'success': False, 'message': 'An error occurred while reporting sighting'}, status=500)

    else:
        print("--- Debug: Received non-POST request for report_sighting ---")
        # Return 405 Method Not Allowed for other request types
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'}, status=405)



@api_view(['GET']) # Use DRF's api_view decorator for GET requests
def get_forest_stations(request):
    """
    Returns a list of all forest stations with their ID and name.
    """
    print("--- Debug: Entered get_forest_stations view ---")
    stations = forest_station.objects.all().order_by('name') # Order by name for consistency
    serializer = ForestStationSerializer(stations, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)




@csrf_exempt
def get_sightings_api(request):
    print("--- Debug: Entered get_sightings_api view ---")
    if request.method == 'GET':
        print(f"--- Debug: Received GET request for /api/sightings/ with params: {request.GET} ---")
        user_id_str = request.GET.get('user_id') # RegularUserLogin ID of the owner of sightings
        if not user_id_str:
            return JsonResponse({'success': False, 'message': 'User ID is required'}, status=400)
        try:
            regular_user_login_id = int(user_id_str)
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid User ID format'}, status=400)

        try:
            # This is the RegularUserLogin instance whose sightings are being fetched
            sighting_owner_regular_user = RegularUserLogin.objects.get(id=regular_user_login_id)
            # Find the user_table instance linked to this RegularUserLogin
            user_profile = user_table.objects.get(REGULAR_LOGIN=sighting_owner_regular_user)

            # Start with sightings reported by this user
            user_sightings_qs = user_upload.objects.filter(USER=user_profile).select_related(
                'station' # For station_name
            ).annotate(
                like_count=Count('likes__id', distinct=True) # Annotate with like count
            )

            # 1. Apply Status Filter
            status_filter = request.GET.get('status')
            if status_filter:
                valid_statuses = [choice[0] for choice in user_upload.STATUS_CHOICES]
                if status_filter in valid_statuses:
                    user_sightings_qs = user_sightings_qs.filter(status=status_filter)
                    print(f"--- Debug (get_sightings_api): Applied status filter: {status_filter} ---")
                else:
                    print(f"--- Debug (get_sightings_api): Invalid status filter received: {status_filter} ---")
                    # Optionally, return an error or ignore

            # 2. Apply Search Term Filter
            search_query = request.GET.get('search_term')
            if search_query:
                user_sightings_qs = user_sightings_qs.filter(
                    Q(animal__icontains=search_query) |
                    Q(animal_type__icontains=search_query) |
                    Q(location_details__icontains=search_query) |
                    Q(station__name__icontains=search_query) # Search by station name
                    # No need to search by username here, as all sightings are from the same user
                )
                print(f"--- Debug (get_sightings_api): Applied search query: {search_query} ---")

            # 3. Apply Sorting
            sort_param = request.GET.get('sort')
            if sort_param == 'likes_desc':
                user_sightings_qs = user_sightings_qs.order_by('-like_count', '-date', '-time')
                print(f"--- Debug (get_sightings_api): Applied sort: {sort_param} ---")
            else:
                # Default sort for user's sightings
                user_sightings_qs = user_sightings_qs.order_by('-date', '-time')
                print(f"--- Debug (get_sightings_api): Applied default sort (-date, -time) ---")

            print(f"--- Debug (get_sightings_api): Found {user_sightings_qs.count()} sightings for user_table ID {user_profile.id} after filters/sort ---")

            sightings_list = []
            for sighting in user_sightings_qs: # sighting is instance of user_upload
                # Determine if the sighting_owner_regular_user has liked this particular sighting
                is_liked_by_owner = SightingLike.objects.filter(
                    sighting=sighting,
                    user=sighting_owner_regular_user # The owner of these sightings
                ).exists()

                sighting_data = {
                    'id': sighting.id,
                    'animal_name': sighting.animal,
                    'animal_type': sighting.animal_type,
                    'location_details': sighting.location_details,
                    'date': sighting.date.strftime('%Y-%m-%d') if sighting.date else None,
                    'time': sighting.time.strftime('%H:%M:%S') if sighting.time else None,
                    'latitude': float(sighting.latitude) if sighting.latitude is not None else None,
                    'longitude': float(sighting.longitude) if sighting.longitude is not None else None,
                    'station_name': sighting.station.name if sighting.station else None,
                    'image_url': request.build_absolute_uri(sighting.image.url) if sighting.image and hasattr(sighting.image, 'url') else None,
                    'status': sighting.status,
                    'created_at': sighting.created_at.isoformat() if hasattr(sighting, 'created_at') and sighting.created_at else None,
                    'username': sighting_owner_regular_user.username, # Username of the owner
                    'like_count': sighting.like_count, # From annotation
                    'is_liked_by_owner': is_liked_by_owner, # Specific to this endpoint's context
                    
                }
                sightings_list.append(sighting_data)

            print(f"--- Debug (get_sightings_api): Serialized {len(sightings_list)} sightings ---")
            return JsonResponse({'success': True, 'sightings': sightings_list})

        except user_table.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User profile not found for RegularUserLogin ID'}, status=404)
        except RegularUserLogin.DoesNotExist:
             return JsonResponse({'success': False, 'message': 'RegularUserLogin profile not found'}, status=404)
        except Exception as e:
            import traceback
            print(f"--- Debug (get_sightings_api) Traceback: {traceback.format_exc()} ---")
            print(f"--- Debug (get_sightings_api): An unexpected error: {e} ---")
            return JsonResponse({'success': False, 'message': 'An error occurred while fetching sightings'}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Only GET method allowed'}, status=405)



@csrf_exempt
def get_all_sightings_api(request):
    print("--- Debug: Entered get_all_sightings_api view ---")
    if request.method == 'GET':
        print(f"--- Debug: Received GET request for /api/all_sightings/ with params: {request.GET} ---")

        requesting_user_id_str = request.GET.get('requesting_user_id')
        requesting_regular_user = None
        if requesting_user_id_str:
            try:
                requesting_regular_user = RegularUserLogin.objects.get(id=int(requesting_user_id_str))
            except (ValueError, RegularUserLogin.DoesNotExist):
                print(f"--- Debug: Invalid or non-existent requesting_user_id: {requesting_user_id_str} ---")
                pass

        try:
            # Start with all sightings
            all_sightings_qs = user_upload.objects.select_related(
                'USER__REGULAR_LOGIN',  # For accessing username
                'USER',                 # Ensure USER is loaded if REGULAR_LOGIN might be null
                'station'               # For accessing station name
            ).annotate(
                like_count=Count('likes__id', distinct=True) # Ensure distinct count for likes
            )

            # 1. Apply Status Filter
            status_filter = request.GET.get('status')
            if status_filter:
                # Validate against your model's choices if necessary, or trust client for now
                # Client sends 'verified', 'pending_investigation'
                # Your model's STATUS_CHOICES keys are 'verified', 'pending_investigation', etc.
                valid_statuses = [choice[0] for choice in user_upload.STATUS_CHOICES]
                if status_filter in valid_statuses:
                    all_sightings_qs = all_sightings_qs.filter(status=status_filter)
                    print(f"--- Debug: Applied status filter: {status_filter} ---")
                else:
                    print(f"--- Debug: Invalid status filter received: {status_filter} ---")
                    # Optionally, return an error or ignore
                    # return JsonResponse({'success': False, 'message': f'Invalid status value: {status_filter}'}, status=400)


            # 2. Apply Search Term Filter
            search_query = request.GET.get('search_term')
            if search_query:
                all_sightings_qs = all_sightings_qs.filter(
                    Q(animal__icontains=search_query) |
                    Q(animal_type__icontains=search_query) |
                    Q(location_details__icontains=search_query) |
                    Q(USER__REGULAR_LOGIN__username__icontains=search_query) | # Search by username
                    Q(station__name__icontains=search_query) # Search by station name
                )
                print(f"--- Debug: Applied search query: {search_query} ---")

            # 3. Apply Sorting
            sort_param = request.GET.get('sort')
            if sort_param == 'likes_desc':
                # Order by like_count descending, then by date/time as secondary
                all_sightings_qs = all_sightings_qs.order_by('-like_count', '-date', '-time')
                print(f"--- Debug: Applied sort: {sort_param} ---")
            else:
                # Default sort if no specific sort or an unrecognized sort is given
                all_sightings_qs = all_sightings_qs.order_by('-date', '-time')
                print(f"--- Debug: Applied default sort (-date, -time) ---")


            print(f"--- Debug: Query (after filters/sort) for all_sightings found {all_sightings_qs.count()} items ---")

            sightings_list = []
            for sighting in all_sightings_qs: # Sighting here is an instance of user_upload
                s_user_profile = sighting.USER # This is user_table instance
                username_display = "Unknown User"

                # Access username through RegularUserLogin linked to user_table
                if s_user_profile and hasattr(s_user_profile, 'REGULAR_LOGIN') and s_user_profile.REGULAR_LOGIN:
                    username_display = s_user_profile.REGULAR_LOGIN.username
                elif s_user_profile and hasattr(s_user_profile, 'first_name') and s_user_profile.first_name: # Fallback
                    username_display = s_user_profile.first_name


                is_liked_by_req_user = False
                if requesting_regular_user:
                    is_liked_by_req_user = SightingLike.objects.filter(
                        sighting=sighting,
                        user=requesting_regular_user
                    ).exists()

                sighting_data = {
                    'id': sighting.id,
                    'animal_name': sighting.animal,
                    'animal_type': sighting.animal_type,
                    'location_details': sighting.location_details,
                    'date': sighting.date.strftime('%Y-%m-%d') if sighting.date else None,
                    'time': sighting.time.strftime('%H:%M:%S') if sighting.time else None,
                    'latitude': float(sighting.latitude) if sighting.latitude is not None else None, # Ensure float for JSON
                    'longitude': float(sighting.longitude) if sighting.longitude is not None else None, # Ensure float for JSON
                    'station_name': sighting.station.name if sighting.station else None,
                    'image_url': request.build_absolute_uri(sighting.image.url) if sighting.image and hasattr(sighting.image, 'url') else None,
                    'status': sighting.status,
                    'created_at': sighting.created_at.isoformat() if hasattr(sighting, 'created_at') and sighting.created_at else None,
                    'username': username_display,
                    'like_count': sighting.like_count,
                    'is_liked_by_requesting_user': is_liked_by_req_user
                }
                sightings_list.append(sighting_data)

            print(f"--- Debug: Serialized {len(sightings_list)} sightings ---")
            return JsonResponse({'success': True, 'sightings': sightings_list})
        except Exception as e:
            import traceback
            print(f"--- Debug Traceback: {traceback.format_exc()} ---") # More detailed error
            print(f"--- Debug: An unexpected error in get_all_sightings_api: {str(e)} ---")
            return JsonResponse({'success': False, 'message': 'An error occurred while fetching all sightings'}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Only GET method allowed'}, status=405)


@csrf_exempt
def toggle_like_sighting_api(request, sighting_id):
    print(f"--- Debug: Entered toggle_like_sighting_api for sighting_id: {sighting_id} ---")
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id_str = data.get('user_id') # This is the RegularUserLogin ID

            if not user_id_str:
                return JsonResponse({'success': False, 'message': 'User ID is required in request body'}, status=400)

            try:
                liking_user_id = int(user_id_str)
                sighting_instance = user_upload.objects.get(id=sighting_id)
                liking_user_instance = RegularUserLogin.objects.get(id=liking_user_id)
            except ValueError:
                return JsonResponse({'success': False, 'message': 'Invalid User ID format'}, status=400)
            except user_upload.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Sighting not found'}, status=404)
            except RegularUserLogin.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Liking user not found'}, status=404)

            # Check if the like already exists
            like_instance, created = SightingLike.objects.get_or_create(
                sighting=sighting_instance,
                user=liking_user_instance
            )

            if created:
                action_message = 'Sighting liked successfully.'
                is_liked = True
            else:
                # Like already existed, so delete it (unlike)
                like_instance.delete()
                action_message = 'Sighting unliked successfully.'
                is_liked = False
            
            # Get the new like count for this sighting
            current_like_count = SightingLike.objects.filter(sighting=sighting_instance).count()

            return JsonResponse({
                'success': True, 
                'message': action_message, 
                'is_liked': is_liked,
                'like_count': current_like_count
            })

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON in request body'}, status=400)
        except Exception as e:
            print(f"--- Debug: Error in toggle_like_sighting_api: {str(e)} ---")
            # import traceback
            # print(f"--- Debug Traceback: {traceback.format_exc()} ---")
            return JsonResponse({'success': False, 'message': 'An error occurred'}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'}, status=405)



@csrf_exempt # Allow GET requests without CSRF token for simplicity in development
def get_forest_stations_api(request):
    print("--- Debug: Entered get_forest_stations_api view ---")

    if request.method == 'GET':
        print("--- Debug: Received GET request for forest stations ---")

        try:
            # Fetch all forest stations, ordered by name
            # Use select_related('DIVISION') if you need division details later
            forest_stations = forest_station.objects.all().order_by('name')
            print(f"--- Debug: Found {forest_stations.count()} forest stations ---")

            # Manually serialize the queryset to a list of dictionaries
            stations_list = []
            for station in forest_stations:
                station_data = {
                    'id': station.id,
                    'name': station.name,
                    'place': station.place,
                    'phone': station.phone,
                    # You could include division details if needed:
                    # 'division_name': station.DIVISION.name if station.DIVISION else None
                }
                stations_list.append(station_data)

            print(f"--- Debug: Serialized {len(stations_list)} forest stations ---")

            # Return the list of stations as a JSON response
            return JsonResponse({'success': True, 'forest_stations': stations_list})

        except Exception as e:
            print(f"--- Debug: An unexpected error occurred while fetching forest stations: {e} ---")
            # Return a generic 500 error response
            return JsonResponse({'success': False, 'message': 'An error occurred while fetching forest stations'}, status=500)

    else:
        print("--- Debug: Received non-GET request for forest stations ---")
        # Return 405 Method Not Allowed for other request types
        return JsonResponse({'success': False, 'message': 'Only GET method allowed'}, status=405)


# ## Android--------ends here-----------------####


def forest_officer_view_user_report(request):
    # Check if user is authenticated and is an officer
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    login_id = request.session.get('user_id')
    if not login_id:
        # It's good practice to handle cases where user_id might be missing from session
        return HttpResponse('''<script> alert('Session error: User ID not found. Please log in again.'); window.location='{}'</script>'''.format(reverse('login')))

    try:
        # Find the officer linked to the login session
        current_officer = forest_officer.objects.get(LOGIN_id=login_id) # Assuming LOGIN is a ForeignKey to login_table
        officer_station = current_officer.STATION # Get the station associated with the officer
    except forest_officer.DoesNotExist:
        return HttpResponse('''<script> alert('Officer profile not found for the logged-in user.'); window.location='{}'</script>'''.format(reverse('login')))
    except Exception as e:
        # Log the error e for debugging
        print(f"Error retrieving officer or station: {e}")
        return HttpResponse('''<script> alert('An error occurred while fetching officer details.'); window.history.back();</script>''')

    # Fetch user reports filtered by the officer's station
    # The user_upload model has a 'station' ForeignKey field linking to forest_station
    reports = user_upload.objects.filter(station=officer_station)

    # Pass the status choices to the template
    status_choices = user_upload.STATUS_CHOICES

    return render(request, 'Forest Officer/View_User_Reports.html', {'reports': reports, 'status_choices': status_choices})

# New view to update report status
def forest_officer_update_report_status(request, report_id, new_status):
    # Check if user is authenticated and is an officer
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    # Get the specific report or return 404
    report = get_object_or_404(user_upload, id=report_id)

    # Validate the new_status against the model's choices
    valid_statuses = [choice[0] for choice in user_upload.STATUS_CHOICES]
    if new_status not in valid_statuses:
        # Handle invalid status - perhaps show an error message
        return render(request, 'error.html', {'message': f'Invalid status: {new_status}'}, status=400) # Bad Request

    # Update the status
    report.status = new_status
    report.save()

    # Redirect back to the view reports page
    return redirect('forest_officer_view_user_report')


# Keep the edit and delete views, they are for more general report management

def forest_officer_edit_user_report(request, report_id):
    # Check if user is authenticated and is an officer
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    # Get the specific report or return 404
    report = get_object_or_404(user_upload, id=report_id)

    if request.method == 'POST':
        form = UserUploadForm(request.POST, instance=report)
        if form.is_valid():
            form.save()
            return redirect('forest_officer_view_user_report') # Redirect after successful edit
    else:
        form = UserUploadForm(instance=report) # Pre-populate form with existing data

    return render(request, 'Forest Officer/Edit_User_Report.html', {'form': form, 'report': report})


def forest_officer_delete_user_report(request, report_id):
    # Check if user is authenticated and is an officer
    if not is_forest_officer(request):
        return redirect_if_not_officer(request)

    # Get the specific report or return 404
    report = get_object_or_404(user_upload, id=report_id)

    if request.method == 'POST':
        report.delete()
        return redirect('forest_officer_view_user_report') # Redirect after successful deletion

    # For GET request, show a confirmation page
    return render(request, 'Forest Officer/Confirm_Delete_User_Report.html', {'report': report})



#User Complaints Android API---------------------------------------------------------------

@api_view(['GET'])
def get_forest_stations(request):
    try:
        stations = forest_station.objects.all().order_by('name')
        serializer = ForestStationSerializer(stations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# NEW: API to get Forest Officer details for a given Station ID
@api_view(['GET'])
def get_officer_by_station(request, station_id):
    try:
        # Get the forest station by ID
        station = forest_station.objects.get(id=station_id)
        
        # Get the forest officer associated with this station
        # Assuming one officer per station for simplicity, or select primary officer
        officer = forest_officer.objects.filter(STATION=station).first()

        if officer:
            serializer = ForestOfficerSerializer(officer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'No officer found for this station.'}, status=status.HTTP_404_NOT_FOUND)
    except forest_station.DoesNotExist:
        return Response({'error': 'Forest station not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# NEW: API to submit a complaint

@api_view(['POST'])
@csrf_exempt
def submit_complaint(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            station_id = data.get('station_id')
            complaint_text = data.get('complaint_text')
            contact_number = data.get('contact_number')

            print(f"DEBUG (submit_complaint): Received user_id: '{user_id}', station_id: '{station_id}'")

            if not all([user_id, station_id, complaint_text, contact_number]):
                print("DEBUG (submit_complaint): Missing required fields. Returning 400.")
                return JsonResponse({'success': False, 'message': 'Missing required fields (user_id, station_id, complaint_text, or contact_number).'}, status=400)

            try:
                # Attempt to get RegularUserLogin
                regular_user_login = RegularUserLogin.objects.get(id=user_id)
                print(f"DEBUG (submit_complaint): Found RegularUserLogin for id {user_id}. Username: {regular_user_login.username}")

                # Check if user_table profile exists using filter().exists() first
                if not user_table.objects.filter(REGULAR_LOGIN=regular_user_login).exists():
                    print(f"DEBUG (submit_complaint): user_table profile DOES NOT exist for RegularUserLogin ID: {user_id}.")
                    # This is the exact condition causing your "User profile not found" message
                    return JsonResponse({'success': False, 'message': 'User profile not found for this login.'}, status=404)

                # If exists() returns True, then try to get the object
                user_profile = user_table.objects.get(REGULAR_LOGIN=regular_user_login)
                print(f"DEBUG (submit_complaint): Successfully retrieved user_table profile for RegularUserLogin ID: {user_id}. Profile ID: {user_profile.id}")

                # Attempt to get ForestStation
                forest_station_obj = forest_station.objects.get(id=station_id)
                print(f"DEBUG (submit_complaint): Found ForestStation for id {station_id}. Name: {forest_station_obj.name}")

            except RegularUserLogin.DoesNotExist:
                print(f"DEBUG (submit_complaint): RegularUserLogin.DoesNotExist triggered for ID: {user_id}.")
                print(traceback.format_exc()) # Print full traceback
                return JsonResponse({'success': False, 'message': 'Regular User Login not found.'}, status=404)
            except user_table.DoesNotExist:
                # This block would only be hit if the filter().exists() above was skipped or returned true incorrectly.
                # It's here for robust error handling, but indicates a deeper logic issue if hit after the exists() check.
                print(f"DEBUG (submit_complaint): user_table.DoesNotExist triggered for RegularUserLogin ID: {user_id}. This is unexpected if filter().exists() passed.")
                print(traceback.format_exc()) # Print full traceback
                return JsonResponse({'success': False, 'message': 'User profile not found for this login.'}, status=404)
            except forest_station.DoesNotExist:
                print(f"DEBUG (submit_complaint): forest_station.DoesNotExist triggered for ID: {station_id}.")
                print(traceback.format_exc()) # Print full traceback
                return JsonResponse({'success': False, 'message': 'Selected Forest Station not found.'}, status=404)
            except Exception as e:
                # Catch any other unexpected errors during object retrieval
                print(f"DEBUG (submit_complaint): An unexpected error during object retrieval: {e}")
                print(traceback.format_exc()) # Print full traceback
                return JsonResponse({'success': False, 'message': f'An unexpected error during retrieval: {str(e)}'}, status=500)

            # If all objects are found, proceed with complaint creation
            complaint_obj = complaints.objects.create(
                USER=user_profile,
                STATION=forest_station_obj,
                complaint=complaint_text,
                contact_number=contact_number,
                reply=""
            )
            print(f"DEBUG (submit_complaint): Complaint created successfully with ID: {complaint_obj.id}")
            return JsonResponse({'success': True, 'message': 'Complaint submitted successfully.', 'complaint_id': complaint_obj.id}, status=201)

        except json.JSONDecodeError:
            print(f"DEBUG (submit_complaint): Invalid JSON format in request body: {request.body.decode('utf-8')}")
            return JsonResponse({'success': False, 'message': 'Invalid JSON format.'}, status=400)
        except Exception as e:
            print(f"DEBUG (submit_complaint): Top-level Exception caught: {e}")
            print(traceback.format_exc()) # Print full traceback for any unhandled errors
            return JsonResponse({'success': False, 'message': f'Error submitting complaint: {str(e)}'}, status=500)
    
    print("DEBUG (submit_complaint): Invalid request method. Returning 405.")
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)


# --- NEW: API View for Regular Users to see their complaints and replies ---
@csrf_exempt # Use this if not using Django's CSRF tokens (common for mobile APIs)
def api_user_my_complaints(request, user_id):
    if request.method == 'GET':
        try:
            # Find the RegularUserLogin instance by the provided user_id
            regular_user_login = RegularUserLogin.objects.get(id=user_id)
            # Find the user_table profile linked to that RegularUserLogin
            user_profile = user_table.objects.get(REGULAR_LOGIN=regular_user_login)

            # Fetch all complaints submitted by this specific user with select_related
            my_complaints = complaints.objects.select_related('USER', 'STATION').filter(USER=user_profile).order_by('-timestamp')

            # Prepare data for JSON response
            complaints_data = []
            for complaint in my_complaints:
                complaints_data.append({
                    'id': complaint.id,
                    'complaint_text': complaint.complaint,
                    'contact_number': str(complaint.contact_number), # Convert BigIntegerField to string
                    'station_name': complaint.STATION.name if complaint.STATION else 'N/A', # Handle potential null station
                    'submitted_on': complaint.timestamp.isoformat(), # ISO 8601 format for date/time
                    'reply': complaint.reply if complaint.reply else "No reply yet.", # Send "No reply yet." if empty
                    'has_reply': bool(complaint.reply) # Boolean flag to indicate if a reply exists
                })

            return JsonResponse({'success': True, 'complaints': complaints_data}, status=200)

        except RegularUserLogin.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Regular User Login not found.'}, status=404)
        except user_table.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User profile not found for this login ID.'}, status=404)
        except Exception as e:
            print(f"An unexpected error occurred in api_user_my_complaints: {e}")
            return JsonResponse({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)


#---------------

@api_view(['POST'])
@csrf_exempt
def delete_complaint(request, complaint_id):
    """
    Allows a regular user to delete their own complaint.
    Requires the user_id to be passed in the request body for authorization.
    This now accepts POST requests due to client-side limitations with DELETE bodies.
    """
    # The request method will now be POST, so no need for if request.method == 'DELETE'
    try:
        # --- DEBUGGING PRINTS (Keep these for now if you like, remove in production) ---
        print(f"DEBUG: Request received for complaint_id: {complaint_id}")
        print(f"DEBUG: Request method: {request.method}") # Should be POST now
        print(f"DEBUG: Request content type: {request.content_type}") # Should be application/json
        print(f"DEBUG: Raw request body: {request.body.decode('utf-8')}")
        # --- END DEBUGGING PRINTS ---

        # Use json.loads(request.body) directly if not using DRF's Request object for parsing
        # If @api_view is used, request.data is usually automatically parsed.
        # But given your previous `request.data` debugging, it's safer to be explicit
        # or stick to json.loads(request.body) if you're not fully leveraging DRF's Request object.
        data = json.loads(request.body) # <--- Explicitly parse JSON body

        # Verify if data is empty or not a dictionary-like object
        if not isinstance(data, dict):
            print(f"DEBUG: request.data is not a dictionary: {type(data)}")
            return JsonResponse({"success": False, "message": "Invalid request data format."}, status=400)

        # --- FIX: Change 'regular_login_id' to 'user_id' here ---
        user_id_from_app = data.get('user_id')
        print(f"DEBUG: Retrieved user_id from request body: {user_id_from_app}")


        if user_id_from_app is None: # Check for None explicitly
            return JsonResponse({"success": False, "message": "Authentication information (user_id) missing in request body."}, status=400)

        try:
            # First, find the RegularUserLogin instance using the user_id from the app
            requesting_regular_user = RegularUserLogin.objects.get(id=user_id_from_app)
            # Then, find the associated user_table profile
            requesting_user_profile = user_table.objects.get(REGULAR_LOGIN=requesting_regular_user)
            print(f"DEBUG: Found user profile for user_id: {user_id_from_app}")
        except RegularUserLogin.DoesNotExist:
            print(f"DEBUG: RegularUserLogin.DoesNotExist for ID: {user_id_from_app}")
            return JsonResponse({'success': False, 'message': 'Requesting user (RegularUserLogin) not found.'}, status=403)
        except user_table.DoesNotExist:
            print(f"DEBUG: user_table.DoesNotExist for REGULAR_LOGIN: {requesting_regular_user.id}")
            return JsonResponse({'success': False, 'message': 'User profile not found for this login.'}, status=403)

        try:
            complaint = complaints.objects.get(pk=complaint_id) # Use complaints model (lowercase)
            print(f"DEBUG: Found complaint with ID: {complaint_id}")
        except complaints.DoesNotExist: # Use complaints model (lowercase)
            print(f"DEBUG: Complaint with ID {complaint_id} not found.")
            return JsonResponse({"success": False, "message": "Complaint not found."}, status=404)

        # Authorization check: Ensure the complaint belongs to the requesting user
        if complaint.USER != requesting_user_profile:
            print(f"DEBUG: Authorization failed: Complaint user ({complaint.USER.id}) != Requesting user ({requesting_user_profile.id})")
            return JsonResponse({"success": False, "message": "You are not authorized to delete this complaint."}, status=403)

        complaint.delete()
        print(f"DEBUG: Complaint ID {complaint_id} deleted successfully.")
        return JsonResponse({"success": True, "message": f"Complaint ID {complaint_id} deleted successfully."})

    except json.JSONDecodeError:
        print(f"DEBUG: JSONDecodeError: {request.body.decode('utf-8')}")
        return JsonResponse({"success": False, "message": "Invalid JSON format in request body."}, status=400)
    except Exception as e:
        print(f"DEBUG: An unexpected error occurred in delete_complaint: {e}")
        return JsonResponse({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}, status=500)




# --- End API View ---


def forest_officer_send_report_to_admin(request):
    return  render(request, 'Forest Officer/Send_Officer_Report.html')


def forest_officer_view_admin_notification(request):
    return  render(request, 'Forest Officer/View_Admin_Notification.html')


def forest_officer_view_dangerous_spot(request):
    return  render(request, 'Forest Officer/View_Dangerous_Spot.html')

def forest_officer_view_trekking_requests(request):
    return  render(request, 'Forest Officer/View_Trekking_Requests_from_User.html')


# --- Modified alerts_trend_data view ---

def alerts_trend_data(request):
    # --- Add Authentication and Authorization Check ---
    # Check if user is authenticated and is an officer
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        # Return a JSON error response for API endpoint
        return JsonResponse({'error': 'Unauthorized'}, status=403) # Use 403 Forbidden status

    # Get the logged-in officer's station
    # *** Use 'user_id' from session ***
    login_id = request.session.get('user_id')
    if not login_id:
         # This case should ideally be caught by the authentication check above, but is a good fallback
         return JsonResponse({'error': 'Session error: User ID not found.'}, status=401) # Use 401 Unauthorized

    try:
        officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station = officer.STATION # Get the station associated with the officer
    except ObjectDoesNotExist:
        # Officer profile not found for the logged-in user
        return JsonResponse({'error': 'Officer profile not found.'}, status=404) # Use 404 Not Found
    except Exception as e:
         print(f"Error retrieving officer/station for trend data: {e}")
         return JsonResponse({'error': 'An error occurred retrieving officer station.'}, status=500) # Use 500 Internal Server Error
    # --- End Authentication/Authorization ---


    # Calculate the start and end dates for the last 7 full days
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6) # Include today

    # Get alerts from the last 7 days, grouping by date and counting
    # --- Add filtering by the officer's station ---
    alerts_by_day = camera_alerts.objects \
        .filter(
            date__gte=seven_days_ago,
            date__lte=today,
            CAMERA__station=officer_station # Add this filter!
        ) \
        .values('date') \
        .annotate(count=Count('id')) \
        .order_by('date')
    # ---------------------------------------------

    # Prepare data structure for the frontend (labels and counts for 7 days)
    labels = []
    data = []
    # Convert the queryset result into a dictionary for easier lookup by date
    counts_dict = {item['date']: item['count'] for item in alerts_by_day}

    # Loop through the last 7 days (from 6 days ago up to today)
    for i in range(7):
        current_date = seven_days_ago + timedelta(days=i)
        # Format date for label (e.g., 'May 17')
        label = current_date.strftime('%b %d')
        # Get count for the current_date, default to 0 if no alerts on that day
        count = counts_dict.get(current_date, 0)

        labels.append(label)
        data.append(count)

    # Return the data as a JSON response
    return JsonResponse({
        'labels': labels,
        'data': data
    })




# New SAFETY Tip----------------------------:

def _check_admin_auth(request):
    """
    Checks if the user is authenticated and has 'admin' type.
    Returns True if authorized, False otherwise.
    """
    return request.session.get('is_authenticated') and request.session.get('user_type') == 'admin'

# --- Custom Admin Views for Safety Tips ---

def admin_add_safety_tip(request):
    """
    Displays the form for adding a new safety tip.
    """
    if not _check_admin_auth(request):
        if request.session.get('user_type') == 'officer':
            return redirect(reverse('forest_officer_home')) # Redirect to officer home if not admin
        else:
            return redirect(reverse('login')) # Redirect to login if not authenticated

    return render(request, 'Admin/Add_Safety_Tip.html')

def admin_add_safety_tip_post(request):
    """
    Handles the POST request for adding a new safety tip.
    """
    if not _check_admin_auth(request):
        if request.session.get('user_type') == 'officer':
            return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login'))

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        category = request.POST.get('category', '')
        content_type = request.POST.get('content_type')
        thumbnail_file = request.FILES.get('thumbnail') # Get the actual UploadedFile object

        if not all([title, content_type, thumbnail_file]):
            return HttpResponse("<script> alert('Title, Content Type, and Thumbnail are required.'); window.history.back(); </script>")

        new_tip = None # Initialize new_tip for cleanup in case of error
        fs = FileSystemStorage() # Initialize FileSystemStorage for potential manual deletions

        try:
            with transaction.atomic(): # Ensure atomicity for database operations
                new_tip = SafetyTip(
                    title=title,
                    description=description,
                    category=category,
                    content_type=content_type,
                    thumbnail=thumbnail_file # Assign the UploadedFile object directly
                )
                new_tip.save() # This saves the tip and its thumbnail to MEDIA_ROOT

                if content_type == 'pdf_document':
                    pdf_file = request.FILES.get('pdf_file')
                    if not pdf_file:
                        raise ValueError("PDF file is required when content type is PDF Document.")
                    
                    new_tip.pdf_file = pdf_file # Assign the UploadedFile object directly
                    new_tip.save(update_fields=['pdf_file']) # Save again to update pdf_file field

                elif content_type == 'image_gallery':
                    image_files = request.FILES.getlist('new_image_files') # Changed to new_image_files
                    captions = request.POST.getlist('new_image_captions') # Changed to new_image_captions

                    if not image_files:
                        raise ValueError("At least one image is required for Image Gallery type.")

                    for i, img_file in enumerate(image_files):
                        caption = captions[i] if i < len(captions) else ''
                        SafetyTipImage.objects.create(
                            safety_tip=new_tip,
                            image=img_file, # Assign the UploadedFile object directly
                            caption=caption,
                            order=i
                        )
            return HttpResponse('''<script> alert('Safety Tip Added Successfully!'); window.location='/safety-tips/view/'; </script>''')

        except ValueError as e:
            # Clean up uploaded files and partially created tip if validation fails
            if new_tip and new_tip.pk: # If tip was created but images/pdf failed
                # Delete files saved via model field first
                if new_tip.thumbnail and fs.exists(new_tip.thumbnail.path): # Use .path
                    fs.delete(new_tip.thumbnail.path) # Use .path
                if new_tip.pdf_file and fs.exists(new_tip.pdf_file.path): # Use .path
                    fs.delete(new_tip.pdf_file.path)
                for img in new_tip.images.all(): # Loop through any images that might have been saved
                    if img.image and fs.exists(img.image.path): # Use .path
                        fs.delete(img.image.path)
                new_tip.delete() # Delete the tip itself from the database
            return HttpResponse(f"<script> alert('Error: {e}'); window.history.back(); </script>")
        except Exception as e:
            # General error handling and cleanup
            if new_tip and new_tip.pk:
                if new_tip.thumbnail and fs.exists(new_tip.thumbnail.path): # Use .path
                    fs.delete(new_tip.thumbnail.path)
                if new_tip.pdf_file and fs.exists(new_tip.pdf_file.path): # Use .path
                    fs.delete(new_tip.pdf_file.path)
                for img in new_tip.images.all():
                    if img.image and fs.exists(img.image.path): # Use .path
                        fs.delete(img.image.path)
                new_tip.delete()
            print(f"Error adding safety tip: {e}") # Log the error for debugging
            return HttpResponse(f"<script> alert('An unexpected error occurred: {e}'); window.history.back(); </script>")
    else:
        return HttpResponse("<script> alert('Invalid request method.'); window.location='/safety-tips/add/'; </script>")

# --- View Safety Tips ---
def admin_view_safety_tips(request):
    """
    Views all safety tips, supporting search by title or category.
    """
    if not _check_admin_auth(request):
        if request.session.get('user_type') == 'officer':
            return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login'))

    tips = SafetyTip.objects.all()
    search_term = request.POST.get('search_term', '').strip() # Use POST for search if form is POST

    if search_term:
        tips = tips.filter(Q(title__icontains=search_term) | Q(category__icontains=search_term))

    context = {'tips': tips, 'search_term': search_term}
    return render(request, 'Admin/View_Safety_Tips.html', context)

# --- Edit Safety Tip Views ---
def admin_edit_safety_tip(request, id):
    """
    Handles displaying the edit form and processing updates for a safety tip.
    """
    if not _check_admin_auth(request):
        if request.session.get('user_type') == 'officer':
            return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login'))

    tip = get_object_or_404(SafetyTip, pk=id)
    fs = FileSystemStorage()

    if request.method == 'POST':
        # Get updated data
        tip.title = request.POST.get('title')
        tip.description = request.POST.get('description', '')
        tip.category = request.POST.get('category', '')
        new_content_type = request.POST.get('content_type')
        
        # Validate required fields
        if not all([tip.title, new_content_type]):
            return HttpResponse(f"<script> alert('Title and Content Type are required.'); window.location='/safety-tips/edit/{id}/'; </script>")

        try:
            with transaction.atomic():
                # --- Handle thumbnail update ---
                new_thumbnail_file = request.FILES.get('thumbnail')
                if new_thumbnail_file:
                    # Delete old thumbnail file if it exists
                    if tip.thumbnail:
                        if fs.exists(tip.thumbnail.path):
                            fs.delete(tip.thumbnail.path)
                    tip.thumbnail = new_thumbnail_file # Assign the new UploadedFile object
                # If no new thumbnail is uploaded, tip.thumbnail will retain its old value.

                # --- Handle content type change and file updates ---
                if new_content_type != tip.content_type:
                    # If content type changes, clear old content and its associated files
                    if tip.content_type == 'pdf_document' and tip.pdf_file:
                        if fs.exists(tip.pdf_file.path):
                            fs.delete(tip.pdf_file.path)
                        tip.pdf_file = None # Clear the field
                    elif tip.content_type == 'image_gallery' and tip.images.exists():
                        for img in tip.images.all():
                            if img.image and fs.exists(img.image.path):
                                fs.delete(img.image.path)
                        tip.images.all().delete() # Delete all related SafetyTipImage objects from DB
                    
                    tip.content_type = new_content_type # Update content type in model

                # --- Handle new PDF upload or existing PDF update ---
                if new_content_type == 'pdf_document':
                    pdf_file = request.FILES.get('pdf_file')
                    if pdf_file: # New PDF uploaded
                        if tip.pdf_file: # If there was an old PDF, delete its file
                            if fs.exists(tip.pdf_file.path):
                                fs.delete(tip.pdf_file.path)
                        tip.pdf_file = pdf_file # Assign the new UploadedFile object
                    # For edit, if it's already a PDF and no new file, keep existing.
                    elif not tip.pdf_file and not request.FILES.get('pdf_file'): # Only validate if no new file and no existing one
                         # This check is less strict on edit than add, assumes PDF might be present
                         pass

                # --- Handle image gallery updates ---
                elif new_content_type == 'image_gallery':
                    # 1. Handle deletions of existing images
                    images_to_delete_ids = request.POST.getlist('images_to_delete')
                    if images_to_delete_ids:
                        for img_id in images_to_delete_ids:
                            try:
                                img_obj = tip.images.get(id=img_id)
                                if img_obj.image and fs.exists(img_obj.image.path):
                                    fs.delete(img_obj.image.path)
                                img_obj.delete()
                            except SafetyTipImage.DoesNotExist:
                                print(f"Warning: Attempted to delete non-existent image with ID {img_id}.")
                                pass
                    
                    # 2. Handle updates to existing images (captions and replacements)
                    existing_image_ids_on_form = request.POST.getlist('existing_image_ids')
                    if existing_image_ids_on_form:
                        for img_id in existing_image_ids_on_form:
                            try:
                                img_obj = tip.images.get(id=img_id)
                                
                                # Flag to check if we need to save this image object
                                should_save_image = False

                                # Update caption
                                updated_caption = request.POST.get(f'existing_image_captions_{img_id}', '')
                                if img_obj.caption != updated_caption: # Compare with current object's caption
                                    img_obj.caption = updated_caption
                                    should_save_image = True # Mark for saving
                                
                                # Handle image file replacement
                                replace_file = request.FILES.get(f'replace_image_file_{img_id}')
                                if replace_file:
                                    # Delete old image file
                                    if img_obj.image and fs.exists(img_obj.image.path):
                                        fs.delete(img_obj.image.path)
                                    img_obj.image = replace_file
                                    should_save_image = True # Mark for saving

                                # Save the image object if anything changed
                                if should_save_image:
                                    img_obj.save() 
                            except SafetyTipImage.DoesNotExist:
                                print(f"Warning: Image with ID {img_id} not found for update (it might have been deleted).")
                                pass

                    # 3. Handle adding new images
                    new_image_files = request.FILES.getlist('new_image_files')
                    new_captions = request.POST.getlist('new_image_captions')

                    if new_image_files:
                        # Determine the starting order for new images (after existing ones)
                        max_order = tip.images.aggregate(Max('order'))['order__max'] 
                        next_order = (max_order + 1) if max_order is not None else 0

                        for i, img_file in enumerate(new_image_files):
                            caption = new_captions[i] if i < len(new_captions) else ''
                            SafetyTipImage.objects.create(
                                safety_tip=tip,
                                image=img_file,
                                caption=caption,
                                order=next_order + i 
                            )

                tip.save() # Save the updated SafetyTip object (updates title, description, category, content_type, thumbnail, pdf_file)

            return HttpResponse(f'''<script> alert('Safety Tip Updated Successfully!'); window.location='/safety-tips/view/'; </script>''')

        except ValueError as e:
            return HttpResponse(f"<script> alert('Error: {e}'); window.location='/safety-tips/edit/{id}/'; </script>")
        except Exception as e:
            print(f"Error updating safety tip (ID: {id}): {e}") # Log the error for debugging
            return HttpResponse(f"<script> alert('An unexpected error occurred: {e}'); window.location='/safety-tips/edit/{id}/'; </script>")
    else:
        # GET request: render the edit form
        context = {
            'tip': tip,
            # Pass current images for display in the template
            'current_images': tip.images.all().order_by('order') if tip.content_type == 'image_gallery' else []
        }
        return render(request, 'Admin/Edit_Safety_Tip.html', context)


# --- Delete Safety Tip Views ---
def admin_delete_safety_tip(request, id):
    """
    Handles the deletion of a safety tip and its associated files.
    """
    if not _check_admin_auth(request):
        if request.session.get('user_type') == 'officer':
            return redirect(reverse('forest_officer_home'))
        else:
            return redirect(reverse('login'))

    tip = get_object_or_404(SafetyTip, pk=id)
    fs = FileSystemStorage()

    try:
        with transaction.atomic():
            # Delete thumbnail file
            if tip.thumbnail and fs.exists(tip.thumbnail.path): # Use .path
                fs.delete(tip.thumbnail.path) # Use .path

            # Delete PDF file if exists
            if tip.content_type == 'pdf_document' and tip.pdf_file:
                if fs.exists(tip.pdf_file.path): # Use .path
                    fs.delete(tip.pdf_file.path)
            
            # Delete associated images if it's an image gallery
            # Deleting the SafetyTip object will automatically cascade delete SafetyTipImage objects
            # due to on_delete=models.CASCADE in SafetyTipImage's ForeignKey.
            # However, we still need to manually delete the image files from storage.
            elif tip.content_type == 'image_gallery':
                for img in tip.images.all():
                    if img.image and fs.exists(img.image.path): # Use .path
                        fs.delete(img.image.path)
            
            tip.delete() # This deletes the SafetyTip object and cascades to SafetyTipImage objects

        return HttpResponse('''<script> alert('Safety Tip Deleted Successfully!'); window.location='/safety-tips/view/'; </script>''')

    except Exception as e:
        print(f"Error deleting safety tip: {e}") # Log the error for debugging
        return HttpResponse(f"<script> alert('An error occurred during deletion: {e}'); window.location='/safety-tips/view/'; </script>")



# --- API Views for Android App (using JsonResponse) ---
# These views will return JSON data that your Android app will consume.

def api_list_safety_tips(request):
    """
    API endpoint to list all safety tips.
    Returns JSON data including URLs for thumbnails, PDFs, and gallery images.
    """
    tips = SafetyTip.objects.prefetch_related('images').all().order_by('title') # Order for consistent API response

    data = []
    for tip in tips:
        tip_data = {
            'id': tip.id,
            'title': tip.title,
            'description': tip.description,
            'content_type': tip.content_type,
            'category': tip.category,
            'thumbnail': request.build_absolute_uri(tip.thumbnail.url) if tip.thumbnail else None,
            'pdf_file': request.build_absolute_uri(tip.pdf_file.url) if tip.pdf_file else None,
            'images': []
        }
        if tip.content_type == 'image_gallery':
            # Ensure images are ordered consistently
            for img in tip.images.all().order_by('order'):
                tip_data['images'].append({
                    'id': img.id,
                    'image': request.build_absolute_uri(img.image.url),
                    'caption': img.caption,
                    'order': img.order
                })
        data.append(tip_data)
    
    return JsonResponse(data, safe=False) # safe=False allows non-dict objects (like lists) to be serialized

def api_detail_safety_tip(request, pk):
    """
    API endpoint to get details of a single safety tip by ID.
    """
    try:
        tip = SafetyTip.objects.get(pk=pk)
    except SafetyTip.DoesNotExist:
        return JsonResponse({'error': 'Safety tip not found'}, status=404)
    
    # Manually serialize the single tip
    tip_data = {
        'id': tip.id,
        'title': tip.title,
        'description': tip.description,
        'content_type': tip.content_type,
        'category': tip.category,
        'thumbnail': request.build_absolute_uri(tip.thumbnail.url) if tip.thumbnail else None,
        'pdf_file': request.build_absolute_uri(tip.pdf_file.url) if tip.pdf_file else None,
        'images': []
    }
    if tip.content_type == 'image_gallery':
        for img in tip.images.all().order_by('order'):
            tip_data['images'].append({
                'id': img.id,
                'image': request.build_absolute_uri(img.image.url),
                'caption': img.caption,
                'order': img.order
            })
    
    return JsonResponse(tip_data)


class IsRegularUserOrOfficer(permissions.BasePermission):
    """
    Custom permission to allow regular users to access their own data
    and officers to access relevant data.
    """
    def has_permission(self, request, view):
        # Allow POST requests for TrekkingRequest (user creation) if authenticated as regular user
        if view.action == 'create' and request.session.get('user_type') == 'regular_user':
            return True
        
        # Allow GET/PUT/DELETE for officers based on their specific access later
        if request.session.get('user_type') == 'officer':
            return True
            
        # Allow GET for regular users to list/retrieve their own
        if view.action in ['list', 'retrieve'] and request.session.get('user_type') == 'regular_user':
            return True

        return False # Deny by default

    def has_object_permission(self, request, view, obj):
        # Allow GET/PUT/DELETE for officers if they are reviewing/managing for their station
        if request.session.get('user_type') == 'officer':
            # Check if the officer is assigned to the station related to the request/pass
            officer_id = request.session.get('user_id')
            try:
                officer = forest_officer.objects.get(LOGIN__id=officer_id)
                if isinstance(obj, TrekkingRequest):
                    # Officer can view/manage requests if the user's station is same as officer's
                    # Or if officer is managing requests from any station (if that's the policy)
                    # For now, let's allow officers to see all pending requests for their station.
                    # Or all requests, and then filter in queryset
                    return True # Will be filtered in get_queryset
                if isinstance(obj, TrekkingPass):
                    return obj.issued_by == officer or obj.request.reviewed_by_officer == officer
            except forest_officer.DoesNotExist:
                return False

        # Allow regular users to retrieve/update/delete their own requests/passes
        if request.session.get('user_type') == 'regular_user':
            user_login_id = request.session.get('user_id')
            try:
                current_user_profile = user_table.objects.get(REGULAR_LOGIN__id=user_login_id)
                if isinstance(obj, TrekkingRequest):
                    return obj.user == current_user_profile
                if isinstance(obj, TrekkingPass):
                    return obj.request.user == current_user_profile
            except user_table.DoesNotExist:
                return False
        
        return False
    

# Trekking Request API ViewSet
# --- TrekkingRequest ViewSet ---
class TrekkingRequestViewSet(viewsets.ModelViewSet):
    queryset = TrekkingRequest.objects.all().order_by('-requested_at')
    serializer_class = TrekkingRequestSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        """
        Custom queryset to filter trekking requests based on the logged-in user's role
        and their associated profile (from session data).
        """
        # Check if the authenticated user (from Django's default auth system) is a superuser.
        # Superusers bypass object-level permissions.
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            print("DEBUG (TrekkingRequestViewSet.get_queryset): Current user is a SUPERUSER. Bypassing filtering and returning all requests.")
            return TrekkingRequest.objects.all().order_by('-requested_at')

        session_user_id = self.request.session.get('user_id')
        session_user_type = self.request.session.get('user_type')

        print(f"DEBUG (TrekkingRequestViewSet.get_queryset): Session User ID: {session_user_id}, Type: {session_user_type}")

        if not session_user_id or not session_user_type:
            print("DEBUG (TrekkingRequestViewSet.get_queryset): Authentication information missing in session. Raising PermissionDenied.")
            raise PermissionDenied("Authentication information not found in session. Please log in.")

        if session_user_type == 'officer':
            try:
                officer_profile = forest_officer.objects.get(id=session_user_id)
                print(f"DEBUG (TrekkingRequestViewSet.get_queryset): Officer profile found: {officer_profile.id}")

                if officer_profile.assigned_station:
                    print(f"DEBUG (TrekkingRequestViewSet.get_queryset): Officer {officer_profile.id} is assigned to station ID: {officer_profile.assigned_station.id}. Applying filter.")
                    return TrekkingRequest.objects.filter(station=officer_profile.assigned_station).order_by('-requested_at')
                else:
                    print(f"DEBUG (TrekkingRequestViewSet.get_queryset): Officer {officer_profile.id} is NOT assigned to a station. Returning empty queryset.")
                    return TrekkingRequest.objects.none()
            except forest_officer.DoesNotExist:
                print(f"DEBUG (TrekkingRequestViewSet.get_queryset): forest_officer profile DOES NOT exist for session ID: {session_user_id}. Raising PermissionDenied.")
                raise PermissionDenied("Officer profile not found. Access denied.")
        
        elif session_user_type == 'regular_user':
            try:
                regular_user_profile = user_table.objects.get(REGULAR_LOGIN__id=session_user_id)
                print(f"DEBUG (TrekkingRequestViewSet.get_queryset): Regular user profile found: {regular_user_profile.id}.")
                return TrekkingRequest.objects.filter(user=regular_user_profile).order_by('-requested_at')
            except user_table.DoesNotExist:
                print(f"DEBUG (TrekkingRequestViewSet.get_queryset): user_table profile DOES NOT exist for RegularUserLogin ID: {session_user_id}. Raising PermissionDenied.")
                raise PermissionDenied("Regular user profile not found. Access denied.")
        
        else:
            print(f"DEBUG (TrekkingRequestViewSet.get_queryset): Unknown or invalid user_type '{session_user_type}' in session. Returning empty queryset.")
            return TrekkingRequest.objects.none()


    def perform_create(self, serializer):
        session_user_id = self.request.session.get('user_id')
        session_user_type = self.request.session.get('user_type')

        print(f"DEBUG (TrekkingRequestViewSet.perform_create): Session User ID: {session_user_id}, Type: {session_user_type}")

        if not session_user_id or session_user_type != 'regular_user':
            raise PermissionDenied("Only authenticated regular users can submit trekking requests.")

        try:
            regular_user_profile = user_table.objects.get(REGULAR_LOGIN__id=session_user_id)
            print(f"DEBUG (TrekkingRequestViewSet.perform_create): Creating request for user_table ID: {regular_user_profile.id}")
            serializer.save(user=regular_user_profile)
        except user_table.DoesNotExist:
            raise PermissionDenied("User profile not found for the logged-in regular user.")
        except Exception as e:
            print(f"DEBUG (TrekkingRequestViewSet.perform_create): Error during creation: {e}")
            raise serializers.ValidationError({"detail": f"Error creating trekking request: {e}"})


    @action(detail=True, methods=['post'])
    def approve_request(self, request, pk=None):
        trekking_request = get_object_or_404(TrekkingRequest, pk=pk)
        
        session_user_id = request.session.get('user_id')
        session_user_type = request.session.get('user_type')

        if not session_user_id or session_user_type != 'officer':
            raise PermissionDenied("Permission denied. Only officers can approve requests.")

        try:
            officer_profile = forest_officer.objects.get(id=session_user_id)
        except forest_officer.DoesNotExist:
            raise PermissionDenied("Officer profile not found.")

        if trekking_request.station != officer_profile.assigned_station:
            print(f"DEBUG (TrekkingRequestViewSet.approve_request): Officer {officer_profile.id} (Station: {officer_profile.assigned_station}) attempted to approve request {trekking_request.id} (Station: {trekking_request.station}). Access denied.")
            raise PermissionDenied("You are not authorized to approve requests for this station.")

        print(f"DEBUG (TrekkingRequestViewSet.approve_request): Officer {officer_profile.id} is authorized to approve request {trekking_request.id}.")

        if trekking_request.status == 'Pending':
            trekking_request.status = 'Approved'
            trekking_request.reviewed_by_officer = officer_profile
            trekking_request.reviewed_at = timezone.now()
            trekking_request.officer_notes = request.data.get('officer_notes', '')
            trekking_request.save()

            pass_content = f"Trekking Pass for Request ID: {trekking_request.id}\n" \
                           f"User: {trekking_request.user.full_name}\n" \
                           f"Destination: {trekking_request.destination}\n" \
                           f"Dates: {trekking_request.start_date} to {trekking_request.end_date}"

            pdf_filename = f"trekking_pass_{trekking_request.id}.pdf"
            pdf_file = ContentFile(pass_content.encode('utf-8'), name=pdf_filename)

            trekking_pass, created = TrekkingPass.objects.update_or_create(
                request=trekking_request,
                defaults={
                    'user_full_name': trekking_request.user.full_name,
                    'issued_by': officer_profile,
                    'pass_pdf': pdf_file,
                    'issued_at': timezone.now()
                }
            )

            serializer = self.get_serializer(trekking_request)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Request cannot be approved. Current status: " + trekking_request.status},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject_request(self, request, pk=None):
        trekking_request = get_object_or_404(TrekkingRequest, pk=pk)

        session_user_id = request.session.get('user_id')
        session_user_type = request.session.get('user_type')

        if not session_user_id or session_user_type != 'officer':
            raise PermissionDenied("Permission denied. Only officers can reject requests.")

        try:
            officer_profile = forest_officer.objects.get(id=session_user_id)
        except forest_officer.DoesNotExist:
            raise PermissionDenied("Officer profile not found.")
        
        if trekking_request.station != officer_profile.assigned_station:
            print(f"DEBUG (TrekkingRequestViewSet.reject_request): Officer {officer_profile.id} (Station: {officer_profile.assigned_station}) attempted to reject request {trekking_request.id} (Station: {trekking_request.station}). Access denied.")
            raise PermissionDenied("You are not authorized to reject requests for this station.")

        print(f"DEBUG (TrekkingRequestViewSet.reject_request): Officer {officer_profile.id} is authorized to reject request {trekking_request.id}.")

        if trekking_request.status == 'Pending':
            trekking_request.status = 'Rejected'
            trekking_request.reviewed_by_officer = officer_profile
            trekking_request.reviewed_at = timezone.now()
            trekking_request.officer_notes = request.data.get('officer_notes', '')
            trekking_request.save()

            TrekkingPass.objects.filter(request=trekking_request).delete()

            serializer = self.get_serializer(trekking_request)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Request cannot be rejected. Current status: " + trekking_request.status},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def get_pending_requests(self, request):
        session_user_id = request.session.get('user_id')
        session_user_type = request.session.get('user_type')

        if not session_user_id or not session_user_type:
            raise PermissionDenied("Authentication information not found in session.")

        if session_user_type == 'officer':
            try:
                officer_profile = forest_officer.objects.get(id=session_user_id)
                if officer_profile.assigned_station:
                    pending_requests = TrekkingRequest.objects.filter(
                        station=officer_profile.assigned_station, 
                        status='Pending'
                    ).order_by('-requested_at')
                else:
                    pending_requests = TrekkingRequest.objects.none()
            except forest_officer.DoesNotExist:
                raise PermissionDenied("Officer profile not found.")
        elif session_user_type == 'regular_user':
            try:
                regular_user_profile = user_table.objects.get(REGULAR_LOGIN__id=session_user_id)
                pending_requests = TrekkingRequest.objects.filter(
                    user=regular_user_profile, 
                    status='Pending'
                ).order_by('-requested_at')
            except user_table.DoesNotExist:
                raise PermissionDenied("Regular user profile not found.")
        else:
            pending_requests = TrekkingRequest.objects.none()
        
        serializer = self.get_serializer(pending_requests, many=True)
        return Response(serializer.data)




    
# --- Trekking Pass API ViewSet ---
class TrekkingPassViewSet(viewsets.ReadOnlyModelViewSet): # ReadOnly for app, officers manage via request review
    queryset = TrekkingPass.objects.all()
    serializer_class = TrekkingPassSerializer
    permission_classes = [IsRegularUserOrOfficer]

    def get_queryset(self):
        user_type = self.request.session.get('user_type')
        user_login_id = self.request.session.get('user_id')

        if user_type == 'regular_user':
            try:
                user_profile = user_table.objects.get(REGULAR_LOGIN__id=user_login_id)
                # User can see only their own passes
                # Assuming TrekkingPass model has a ForeignKey 'request' which has a ForeignKey 'USER'
                return TrekkingPass.objects.filter(request__USER=user_profile).order_by('-issued_at') # Changed 'request__user' to 'request__USER'
            except user_table.DoesNotExist:
                return TrekkingPass.objects.none()
        elif user_type == 'officer':
            try:
                officer = forest_officer.objects.get(LOGIN__id=user_login_id)
                # Officer can see passes they have issued
                return TrekkingPass.objects.filter(issued_by=officer).order_by('-issued_at')
            except forest_officer.DoesNotExist:
                return TrekkingPass.objects.none()
        return TrekkingPass.objects.none()

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        trekking_pass = self.get_object()
        if not trekking_pass.pass_pdf:
            raise Http404("PDF pass not generated for this request.")
        
        # Ensure the user has permission to download this specific pass
        # This will be handled by has_object_permission, but we can double check
        # if not self.get_permissions()[0].has_object_permission(request, self, trekking_pass):
        #     return Response({"detail": "You do not have permission to download this pass."}, status=status.HTTP_403_FORBIDDEN)

        file_path = trekking_pass.pass_pdf.path
        if os.path.exists(file_path):
            return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        else:
            raise Http404("PDF file not found on server.")




# --- Officer Web Views for Trekking Request Management ---

@never_cache
def officer_trekking_requests_list(request):
    """
    Officer view to list pending and reviewed trekking requests,
    filtered by the officer's assigned station.
    """
    if request.session.get('user_type') != 'officer':
        messages.error(request, "Access denied. Only officers can view this page.")
        return redirect('login')

    officer_login_id = request.session.get('user_id')
    officer_profile = None
    try:
        officer_profile = forest_officer.objects.get(LOGIN__id=officer_login_id)
        # Ensure officer has an assigned station to proceed with filtering
        # MODIFIED: Changed assigned_station to STATION
        if not officer_profile.STATION:
            messages.warning(request, "Your officer profile is not assigned to a station. No requests to display.")
            return render(request, 'Forest Officer/TrekkingRequests/trekking_request_list.html', {
                'pending_requests': TrekkingRequest.objects.none(),
                'reviewed_requests': TrekkingRequest.objects.none(),
                'officer': officer_profile,
            })
    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found.")
        return redirect('login')

    
    station_filter = Q(station=officer_profile.STATION)

    # Get requests where status is Pending OR where the officer is the reviewer
    # AND they belong to the officer's assigned station.
    all_requests_for_station = TrekkingRequest.objects.select_related(
        'user', 'station', 'reviewed_by_officer'
    ).filter(
        station_filter & (Q(status='Pending') | Q(reviewed_by_officer=officer_profile))
    ).order_by('-requested_at') # Order by most recent first

    pending_requests = all_requests_for_station.filter(status='Pending')
    reviewed_requests = all_requests_for_station.exclude(status='Pending')

    context = {
        'pending_requests': pending_requests,
        'reviewed_requests': reviewed_requests,
        'officer': officer_profile,
    }
    return render(request, 'Forest Officer/TrekkingRequests/trekking_request_list.html', context)


@api_view(['GET', 'POST']) # Allow POST for submitting review form
@csrf_exempt
def officer_trekking_request_detail(request, pk):
    try:
        user_type = request.session.get('user_type')
        user_login_id = request.session.get('user_id')

        if user_type != 'officer' or not user_login_id:
            messages.error(request, 'Permission denied. Officer login required.')
            return redirect('login')

        officer = get_object_or_404(forest_officer, LOGIN__id=user_login_id)
        request_obj = get_object_or_404(TrekkingRequest, pk=pk) # Renamed to request_obj to match template

        # NEW: Enforce station-based access for detail view as well
        # MODIFIED: Changed assigned_station to STATION
        if request_obj.station != officer.STATION: # FIX: Changed officer.assigned_station to officer.STATION
            messages.error(request, f"Access denied. This request does not belong to your assigned station ({officer.STATION.name}).")
            return redirect('officer_trekking_requests_list')


        current_pass = None
        try:
            current_pass = TrekkingPass.objects.get(request=request_obj)
            print(f"DEBUG (GET): current_pass.pass_pdf: {current_pass.pass_pdf}")
            if current_pass.pass_pdf:
                print(f"DEBUG (GET): current_pass.pass_pdf.url: {current_pass.pass_pdf.url}")
        except TrekkingPass.DoesNotExist:
            print("DEBUG (GET): TrekkingPass does not exist for this request yet.")
            pass

        if request.method == 'POST':
            action = request.POST.get('action')
            officer_notes = request.POST.get('officer_notes', '').strip()

            request_obj.officer_notes = officer_notes
            request_obj.reviewed_by_officer = officer
            request_obj.reviewed_at = timezone.now()

            if action == 'approve':
                valid_from_str = request.POST.get('valid_from')
                valid_to_str = request.POST.get('valid_to')
                instructions = request.POST.get('instructions', '').strip()

                if not all([valid_from_str, valid_to_str, instructions]):
                    messages.error(request, "For approved requests, 'Valid From', 'Valid To', and 'Instructions' are required.")
                    context = {
                        'request_obj': request_obj,
                        'current_pass': current_pass,
                        'officer': officer,
                        'initial_valid_from': valid_from_str,
                        'initial_valid_to': valid_to_str,
                        'initial_instructions': instructions,
                    }
                    return render(request, 'Forest Officer/TrekkingRequests/trekking_request_detail.html', context)

                try:
                    valid_from = timezone.datetime.fromisoformat(valid_from_str)
                    valid_to = timezone.datetime.fromisoformat(valid_to_str)
                    
                    if timezone.is_naive(valid_from):
                        valid_from = timezone.make_aware(valid_from, timezone.get_current_timezone())
                    if timezone.is_naive(valid_to):
                        valid_to = timezone.make_aware(valid_to, timezone.get_current_timezone())

                except ValueError:
                    messages.error(request, "Invalid date/time format for 'Valid From' or 'Valid To'. Use ISO 8601.")
                    context = {
                        'request_obj': request_obj,
                        'current_pass': current_pass,
                        'officer': officer,
                        'initial_valid_from': valid_from_str,
                        'initial_valid_to': valid_to_str,
                        'initial_instructions': instructions,
                    }
                    return render(request, 'Forest Officer/TrekkingRequests/trekking_request_detail.html', context)
                
                request_obj.status = 'Approved'
                request_obj.save()

                if current_pass:
                    pass_obj = current_pass
                else:
                    pass_obj = TrekkingPass(request=request_obj)

                pass_obj.issued_by = officer
                pass_obj.valid_from = valid_from
                pass_obj.valid_to = valid_to
                pass_obj.instructions = instructions
                pass_obj.issued_at = timezone.now()

                pass_obj.save()
                
                print(f"DEBUG (POST): After first save, pass_obj.id: {pass_obj.id}")
                print(f"DEBUG (POST): After first save, pass_obj.issued_at: {pass_obj.issued_at}")
                pdf_buffer = generate_trekking_pass_pdf(pass_obj)
                pdf_filename = f"pass_{pass_obj.request.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.pdf"
                
                pass_obj.pass_pdf.save(pdf_filename, ContentFile(pdf_buffer.getvalue()), save=True)
                pdf_buffer.close()

                
                current_pass = pass_obj
                print(f"DEBUG (POST): After pass_obj.pass_pdf.save(), current_pass.pass_pdf: {current_pass.pass_pdf}")
                if current_pass.pass_pdf:
                    print(f"DEBUG (POST): After pass_obj.pass_pdf.save(), current_pass.pass_pdf.url: {current_pass.pass_pdf.url}")

                messages.success(request, f"Trekking Request #{pk} approved and pass issued successfully!")
                return redirect('officer_trekking_request_detail', pk=pk)

            elif action == 'reject':
                request_obj.status = 'Rejected'
                request_obj.save()
                if current_pass:
                    current_pass.delete()
                    current_pass = None
                messages.info(request, f"Trekking Request #{pk} rejected.")
                return redirect('officer_trekking_request_detail', pk=pk)

        initial_valid_from = None
        initial_valid_to = None
        initial_instructions = ""
        if current_pass:
            initial_valid_from = current_pass.valid_from.strftime('%Y-%m-%dT%H:%M') if current_pass.valid_from else None
            initial_valid_to = current_pass.valid_to.strftime('%Y-%m-%dT%H:%M') if current_pass.valid_to else None
            initial_instructions = current_pass.instructions

        context = {
            'request_obj': request_obj,
            'current_pass': current_pass,
            'officer': officer,
            'initial_valid_from': initial_valid_from,
            'initial_valid_to': initial_valid_to,
            'initial_instructions': initial_instructions,
        }
        return render(request, 'Forest Officer/TrekkingRequests/trekking_request_detail.html', context)

    except forest_officer.DoesNotExist:
        messages.error(request, 'Officer profile not found.')
        return redirect('login')
    except Exception as e:
        print(f"Error in officer_trekking_request_detail: {e}")
        traceback.print_exc()
        messages.error(request, 'An internal server error occurred while processing the request.')
        return redirect('officer_trekking_requests_list')


# --- Get User Profile API View ---
def is_authenticated(request):
    return request.session.get('user_id') is not None and request.session.get('user_type') is not None

# --- New API View for /api/auth/user/ ---
@csrf_exempt
@require_http_methods(["GET"])
def get_current_user_details_api(request): # for fetching user station on animal alerts activity
    if not is_authenticated(request):
        return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)

    authenticated_user_id = request.session.get('user_id')
    
    if not authenticated_user_id:
        # This case should ideally not be reached if is_authenticated passed
        return JsonResponse({'success': False, 'message': 'User ID not found in session.'}, status=401)

    try:
        # Use the authenticated_user_id from the session
        regular_user_login = get_object_or_404(RegularUserLogin, pk=authenticated_user_id)
        user_profile = get_object_or_404(user_table, REGULAR_LOGIN=regular_user_login)

        profile_data = {
            'user_id': regular_user_login.pk, # Good to include the user_id itself
            'first_name': user_profile.first_name,
            'last_name': user_profile.last_name,
            'place': user_profile.place,
            'pin': user_profile.pin if user_profile.pin is not None else "",
            'phone': user_profile.phone if user_profile.phone is not None else "",
            'email': user_profile.email if user_profile.email is not None else "",
            'image': request.build_absolute_uri(user_profile.image.url) if user_profile.image else None,
            'station_id': user_profile.STATION.id if user_profile.STATION else None,
            'station_name': user_profile.STATION.name if user_profile.STATION else None,
        }
        logger.info(f"Successfully fetched profile for current authenticated user_id: {authenticated_user_id}")
        return JsonResponse({'success': True, 'user_profile': profile_data})

    except RegularUserLogin.DoesNotExist:
        logger.warning(f"RegularUserLogin with session ID {authenticated_user_id} not found for profile fetch.")
        # This implies a session exists for a user_id that no longer maps to a RegularUserLogin.
        # This could happen if the user was deleted but their session wasn't cleared.
        # Clearing the session might be a good idea here.
        request.session.flush() # Optional: Clear the invalid session
        return JsonResponse({'success': False, 'message': 'User associated with session not found.'}, status=404)
    except user_table.DoesNotExist:
        logger.warning(f"UserTable profile not found for RegularUserLogin session ID {authenticated_user_id}.")
        return JsonResponse({'success': True, 'user_profile': {
            'user_id': authenticated_user_id, 'first_name': '', 'last_name': '', 'place': '', 'pin': '', 'phone': '', 'email': '', 'image': None, 'station_id': None, 'station_name': None
        }, 'message': 'User profile not complete. Please fill in your details.'}, status=200) # status 200 is fine here
    except Exception as e:
        logger.error(f"Error fetching current user profile for session ID {authenticated_user_id}: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An internal server error occurred.'}, status=500)




@csrf_exempt
@require_http_methods(["GET"])
def get_user_profile_api(request, user_id):
    if not is_authenticated(request):
        return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)

    # Verify that the user_id in the URL matches the authenticated user's ID
    authenticated_regular_user_id = request.session.get('user_id')
    if not authenticated_regular_user_id or str(authenticated_regular_user_id) != str(user_id):
        return JsonResponse({'success': False, 'message': 'Unauthorized: Mismatching user ID.'}, status=403)

    try:
        # Assuming user_id refers to the ID of the RegularUserLogin instance
        regular_user_login = get_object_or_404(RegularUserLogin, pk=user_id)
        # Corrected: Use REGULAR_LOGIN to query user_table
        user_profile = get_object_or_404(user_table, REGULAR_LOGIN=regular_user_login)

        profile_data = {
            'first_name': user_profile.first_name,
            'last_name': user_profile.last_name,
            'place': user_profile.place,
            'pin': user_profile.pin if user_profile.pin is not None else "", # Return empty string if None
            'phone': user_profile.phone if user_profile.phone is not None else "", # Return empty string if None
            'email': user_profile.email if user_profile.email is not None else "", # Return empty string if None
            'image': request.build_absolute_uri(user_profile.image.url) if user_profile.image else None, # Changed 'profile_image' to 'image'
            'station_id': user_profile.STATION.id if user_profile.STATION else None,
            'station_name': user_profile.STATION.name if user_profile.STATION else None,
        }
        logger.info(f"Successfully fetched profile for user_id: {user_id}")
        return JsonResponse({'success': True, 'user_profile': profile_data})

    except RegularUserLogin.DoesNotExist:
        logger.warning(f"RegularUserLogin with ID {user_id} not found for profile fetch.")
        return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)
    except user_table.DoesNotExist:
        logger.warning(f"UserTable profile not found for RegularUserLogin ID {user_id}.")
        # If profile doesn't exist, it means user hasn't completed it yet.
        # Return a success with empty profile data or a specific message to prompt completion.
        return JsonResponse({'success': True, 'user_profile': {
            'first_name': '', 'last_name': '', 'place': '', 'pin': '', 'phone': '', 'email': '', 'image': None, 'station_id': None, 'station_name': None
        }, 'message': 'User profile not complete. Please fill in your details.'}, status=200)
    except Exception as e:
        logger.error(f"Error fetching user profile for ID {user_id}: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An internal server error occurred.'}, status=500)

# --- Update User Profile API View ---
@csrf_exempt
@require_http_methods(["POST"])
def update_user_profile_api(request):
    logger.info(f"Received update_user_profile_api request. Method: {request.method}")
    if not is_authenticated(request):
        logger.warning("Authentication failed for update_user_profile_api.")
        return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)

    try:
        user_id = request.POST.get('user_id')
        logger.info(f"User ID from POST data: {user_id}")
        if not user_id:
            logger.error("User ID is missing from POST data.")
            return JsonResponse({'success': False, 'message': 'User ID is required.'}, status=400)

        # Verify that the user_id in the POST request matches the authenticated user's ID
        authenticated_regular_user_id = request.session.get('user_id')
        logger.info(f"Authenticated user ID from session: {authenticated_regular_user_id}")
        if not authenticated_regular_user_id or str(authenticated_regular_user_id) != user_id:
            logger.warning(f"Unauthorized access attempt for user {user_id}. Authenticated as {authenticated_regular_user_id}.")
            return JsonResponse({'success': False, 'message': 'Unauthorized: Mismatching user ID.'}, status=403)

        regular_user_login = get_object_or_404(RegularUserLogin, pk=user_id)
        # Corrected: Use REGULAR_LOGIN to query user_table
        user_profile, created = user_table.objects.get_or_create(REGULAR_LOGIN=regular_user_login)
        logger.info(f"User profile retrieved/created for RegularUserLogin ID {user_id}. Current STATION: {user_profile.STATION.name if user_profile.STATION else 'None'}")


        # Update profile fields from POST data
        user_profile.first_name = request.POST.get('first_name', user_profile.first_name)
        user_profile.last_name = request.POST.get('last_name', user_profile.last_name)
        user_profile.place = request.POST.get('place', user_profile.place)
        
        pin_str = request.POST.get('pin')
        user_profile.pin = int(pin_str) if pin_str and pin_str.isdigit() else None

        phone_str = request.POST.get('phone')
        user_profile.phone = int(phone_str) if phone_str and phone_str.isdigit() else None

        user_profile.email = request.POST.get('email', user_profile.email)
        if user_profile.email == '':
            user_profile.email = None

        # Update Forest Station
        station_id = request.POST.get('station_id')
        logger.info(f"Received station_id in POST data: {station_id}")
        if station_id:
            try:
                station = forest_station.objects.get(id=station_id)
                user_profile.STATION = station
                logger.info(f"Found station: {station.name} (ID: {station.id}). Assigning to user profile.")
            except forest_station.DoesNotExist:
                logger.error(f"Invalid Forest Station ID provided: {station_id}.")
                return JsonResponse({'success': False, 'message': 'Invalid Forest Station ID provided.'}, status=400)
        else:
            user_profile.STATION = None # Allow setting station to null if not provided
            logger.info("No station_id provided. Setting user_profile.STATION to None.")

        # Handle profile image upload
        if 'image' in request.FILES: # Changed from 'profile_image' to 'image'
            user_profile.image = request.FILES['image'] # Changed from 'profile_image' to 'image'
            logger.info(f"Received new profile image for user {user_id} via file upload.")
        # If you were sending base64, this part would be here:
        # elif 'image_base64' in request.POST:
        #     base64_string = request.POST['image_base64']
        #     format, imgstr = base64_string.split(';base64,')
        #     ext = format.split('/')[-1]
        #     data = ContentFile(base64.b64decode(imgstr), name=f'{user_id}_profile.{ext}')
        #     user_profile.image.save(f'{user_id}_profile.{ext}', data, save=False)
        #     logger.info(f"Received new profile image for user {user_id} via Base64.")

        user_profile.save()
        logger.info(f"User profile saved successfully. New STATION: {user_profile.STATION.name if user_profile.STATION else 'None'}")
        return JsonResponse({'success': True, 'message': 'Profile updated successfully.'})

    except RegularUserLogin.DoesNotExist:
        logger.error(f"RegularUserLogin not found for ID in update_user_profile.")
        return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)
    except Exception as e:
        logger.error(f"Error updating user profile: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An internal server error occurred.'}, status=500)

# --- Change Username API View ---
@csrf_exempt
@require_http_methods(["POST"])
def change_username_api(request):
    logger.info("Received change_username_api request.")
    if not is_authenticated(request):
        logger.warning("Authentication failed for change_username_api.")
        return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)

    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        old_username = data.get('old_username')
        new_username = data.get('new_username')
        password = data.get('password') # Current password for verification

        logger.info(f"Change Username Request: user_id={user_id}, old_username={old_username}, new_username={new_username}")

        if not all([user_id, old_username, new_username, password]):
            logger.error("Missing required fields for change username.")
            return JsonResponse({'success': False, 'message': 'All fields are required.'}, status=400)

        # Verify that the user_id in the request matches the authenticated user's ID
        authenticated_regular_user_id = request.session.get('user_id')
        if not authenticated_regular_user_id or str(authenticated_regular_user_id) != str(user_id):
            logger.warning(f"Unauthorized access attempt for user {user_id} (change username). Authenticated as {authenticated_regular_user_id}.")
            return JsonResponse({'success': False, 'message': 'Unauthorized: Mismatching user ID.'}, status=403)

        try:
            user_login = RegularUserLogin.objects.get(pk=user_id)
        except RegularUserLogin.DoesNotExist:
            logger.error(f"RegularUserLogin with ID {user_id} not found for username change.")
            return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)

        # Verify old username and password
        if user_login.username != old_username:
            logger.warning(f"Old username mismatch for user {user_id}. Provided: {old_username}, Actual: {user_login.username}")
            return JsonResponse({'success': False, 'message': 'Incorrect old username.'}, status=400)

        if not user_login.check_password(password):
            logger.warning(f"Incorrect password for user {user_id} during username change.")
            return JsonResponse({'success': False, 'message': 'Incorrect password.'}, status=400)

        # Check if new username is already taken
        if RegularUserLogin.objects.filter(username=new_username).exclude(pk=user_id).exists():
            logger.warning(f"New username '{new_username}' is already taken.")
            return JsonResponse({'success': False, 'message': 'New username is already taken.'}, status=409)

        user_login.username = new_username
        user_login.save()
        logger.info(f"Username for user {user_id} successfully changed to '{new_username}'.")
        return JsonResponse({'success': True, 'message': 'Username updated successfully.'})

    except json.JSONDecodeError:
        logger.error("Invalid JSON format in change_username_api request body.")
        return JsonResponse({'success': False, 'message': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        logger.error(f"Error changing username: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An internal server error occurred.'}, status=500)

# --- Change Password API View ---
@csrf_exempt
@require_http_methods(["POST"])
def change_password_api(request):
    logger.info("Received change_password_api request.")
    if not is_authenticated(request):
        logger.warning("Authentication failed for change_password_api.")
        return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)

    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        username = data.get('username') # Username for verification
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        logger.info(f"Change Password Request: user_id={user_id}, username={username}")

        if not all([user_id, username, old_password, new_password]):
            logger.error("Missing required fields for change password.")
            return JsonResponse({'success': False, 'message': 'All fields are required.'}, status=400)

        # Verify that the user_id in the request matches the authenticated user's ID
        authenticated_regular_user_id = request.session.get('user_id')
        if not authenticated_regular_user_id or str(authenticated_regular_user_id) != str(user_id):
            logger.warning(f"Unauthorized access attempt for user {user_id} (change password). Authenticated as {authenticated_regular_user_id}.")
            return JsonResponse({'success': False, 'message': 'Unauthorized: Mismatching user ID.'}, status=403)

        try:
            user_login = RegularUserLogin.objects.get(pk=user_id)
        except RegularUserLogin.DoesNotExist:
            logger.error(f"RegularUserLogin with ID {user_id} not found for password change.")
            return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)

        # Verify username (redundant if user_id is already verified, but good for double-check)
        if user_login.username != username:
            logger.warning(f"Username mismatch for user {user_id} during password change. Provided: {username}, Actual: {user_login.username}")
            return JsonResponse({'success': False, 'message': 'Incorrect username.'}, status=400)

        # Verify old password
        if not user_login.check_password(old_password):
            logger.warning(f"Incorrect old password for user {user_id} during password change.")
            return JsonResponse({'success': False, 'message': 'Incorrect old password.'}, status=400)

        user_login.set_password(new_password) # Hash and set new password
        user_login.save()
        logger.info(f"Password for user {user_id} successfully changed.")
        return JsonResponse({'success': True, 'message': 'Password updated successfully.'})

    except json.JSONDecodeError:
        logger.error("Invalid JSON format in change_password_api request body.")
        return JsonResponse({'success': False, 'message': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        logger.error(f"Error changing password: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An internal server error occurred.'}, status=500)


@api_view(['POST'])
@permission_classes([]) # No authentication needed for password reset request
def password_reset_request(request):
    username_or_email = request.data.get('username_or_email')

    if not username_or_email:
        return Response({'success': False, 'message': 'Username or Email is required.'},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        # Try to find user by username or email in RegularUserLogin through user_table
        # This assumes a user_table entry exists for every RegularUserLogin you want to reset
        user_table_entry = user_table.objects.get(
            Q(REGULAR_LOGIN__username=username_or_email) | Q(email=username_or_email)
        )
        regular_user_login = user_table_entry.REGULAR_LOGIN

        if not regular_user_login:
            # This case should ideally not happen if user_table has a REGULAR_LOGIN
            logger.warning(f"User table entry found but no associated RegularUserLogin for: {username_or_email}")
            return Response({'success': True, 'message': 'If an account matching that username or email is found, a password reset email has been sent.'},
                            status=status.HTTP_200_OK)

        if not user_table_entry.email:
            return Response({'success': False, 'message': 'This account does not have an associated email address for password reset.'},
                            status=status.HTTP_400_BAD_REQUEST)

    except user_table.DoesNotExist:
        # IMPORTANT SECURITY CONSIDERATION:
        # To prevent user enumeration, always send a generic success message
        # even if the user doesn't exist. This prevents attackers from guessing
        # valid usernames/emails.
        logger.info(f"Password reset request for non-existent user/email: {username_or_email}")
        return Response({'success': True, 'message': 'If an account matching that username or email is found, a password reset email has been sent.'},
                        status=status.HTTP_200_OK) # Return 200 OK even if user not found

    # Invalidate any existing tokens for this user
    PasswordResetToken.objects.filter(user=regular_user_login).delete()

    # Create a new password reset token
    reset_token = PasswordResetToken.objects.create(user=regular_user_login)

    
    reset_url = f"{settings.FRONTEND_RESET_URL_BASE}/reset_password/{regular_user_login.id}/{reset_token.token}/"

    email_subject = "WildEye Password Reset Request"
    email_template_name = 'emails/password_reset_email.html' # Path to your email template

    # Pass data to the email template context
    context = {
        'user_name': regular_user_login.username,
        'reset_url': reset_url,
        'app_name': 'WildEye App', # Customize your app name
    }

    email_html_message = render_to_string(email_template_name, context)
    email_plaintext_message = f"Hello {regular_user_login.username},\n\nYou requested a password reset for your WildEye account. Please use the following link to reset your password:\n\n{reset_url}\n\nIf you did not request this, please ignore this email.\n\nThank you,\nWildEye Team"

    try:
        send_mail(
            email_subject,
            email_plaintext_message,
            settings.DEFAULT_FROM_EMAIL,
            [user_table_entry.email], # Send to the email from user_table
            html_message=email_html_message, # Send HTML version
            fail_silently=False,
        )
        return Response({'success': True, 'message': 'If an account matching that username or email is found, a password reset email has been sent.'},
                        status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error sending password reset email to {user_table_entry.email}: {e}", exc_info=True)
        return Response({'success': False, 'message': 'Failed to send password reset email. Please try again later.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- New view to handle the password reset from the web link ---
@api_view(['GET', 'POST']) # GET for displaying form, POST for submitting
@permission_classes([])
def reset_password_confirm(request, user_id, token):
    try:
        regular_user_login = RegularUserLogin.objects.get(id=user_id)
    except RegularUserLogin.DoesNotExist:
        # Render an error page or redirect
        return render(request, 'password_reset_invalid.html', {'message': 'Invalid reset link or user.'})

    try:
        reset_token_obj = PasswordResetToken.objects.get(user=regular_user_login, token=token)
    except PasswordResetToken.DoesNotExist:
        return render(request, 'password_reset_invalid.html', {'message': 'Invalid or expired password reset token.'})

    if not reset_token_obj.is_valid():
        reset_token_obj.delete() # Invalidate expired token
        return render(request, 'password_reset_invalid.html', {'message': 'Invalid or expired password reset token. Please request a new one.'})

    if request.method == 'POST':
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not new_password or not confirm_password:
            return render(request, 'password_reset_confirm.html', {'user_id': user_id, 'token': token, 'error': 'All fields are required.'})

        if new_password != confirm_password:
            return render(request, 'password_reset_confirm.html', {'user_id': user_id, 'token': token, 'error': 'Passwords do not match.'})

        if len(new_password) < 6: # Example: minimum password length
             return render(request, 'password_reset_confirm.html', {'user_id': user_id, 'token': token, 'error': 'Password must be at least 6 characters long.'})


        # Set the new password
        regular_user_login.set_password(new_password)
        regular_user_login.save()

        # Invalidate the token after successful password reset
        reset_token_obj.delete()

        return render(request, 'password_reset_success.html')

    return render(request, 'password_reset_confirm.html', {'user_id': user_id, 'token': token})

### Detection laucher for camera alerts----Begins here----------------------------------------------------------------

# Define the path to your web_launcher.py and its working directory dynamically
WEB_LAUNCHER_SCRIPT_PATH = os.path.abspath(os.path.join(settings.BASE_DIR, "..", "tools", "web_launcher.py"))
WEB_LAUNCHER_WORKING_DIR = os.path.abspath(os.path.join(settings.BASE_DIR, "..", "tools"))
WEB_LAUNCHER_URL = "http://localhost:5000" # The URL where web_launcher.py will be accessible

# Keep track of the launcher process (very basic, only for the lifetime of this Django worker)
# For more robust management, external tools are better.
launcher_process = None

def launch_detection_service_launcher(request):
    global launcher_process

    # Determine a fallback URL. Replace 'myapp:forest_officer_home' if that's not always appropriate.
    # For example, if an admin might also click this, you might need a more generic fallback.
    fallback_url_name = 'forest_officer_home' # Default fallback
    if request.session.get('user_type') == 'admin':

        pass # Or redirect to a specific admin page

    referer_url = request.META.get('HTTP_REFERER')
    redirect_url = referer_url if referer_url else reverse(fallback_url_name)


    if not os.path.exists(WEB_LAUNCHER_SCRIPT_PATH):
        messages.error(request, f"Error: Detection service launcher script not found at {WEB_LAUNCHER_SCRIPT_PATH}")
        return redirect(redirect_url)

    if not os.path.isdir(WEB_LAUNCHER_WORKING_DIR):
        messages.error(request, f"Error: Working directory for launcher not found: {WEB_LAUNCHER_WORKING_DIR}")
        return redirect(redirect_url)

    if launcher_process and launcher_process.poll() is None:
        messages.info(request, f"Detection service launcher appears to be already running (PID: {launcher_process.pid}). "
                               f"Try accessing it at: <a href='{WEB_LAUNCHER_URL}' target='_blank' class='alert-link'>{WEB_LAUNCHER_URL}</a>", extra_tags='safe')
    else:
        try:
            command = [sys.executable, WEB_LAUNCHER_SCRIPT_PATH]
            # For better debugging of the subprocess, you can capture its output
            # log_dir = os.path.join(WEB_LAUNCHER_WORKING_DIR, 'logs')
            # os.makedirs(log_dir, exist_ok=True)
            # out_log = open(os.path.join(log_dir, 'launcher_stdout.log'), 'ab')
            # err_log = open(os.path.join(log_dir, 'launcher_stderr.log'), 'ab')
            # launcher_process = subprocess.Popen(command, cwd=WEB_LAUNCHER_WORKING_DIR, stdout=out_log, stderr=err_log)
            
            launcher_process = subprocess.Popen(command, cwd=WEB_LAUNCHER_WORKING_DIR)
            messages.success(request, f"Detection service launcher initiated (PID: {launcher_process.pid}). "
                                      f"Please allow a few moments for it to start, then access it at: "
                                      f"<a href='{WEB_LAUNCHER_URL}' target='_blank' class='alert-link'>{WEB_LAUNCHER_URL}</a>", extra_tags='safe')
            print(f"Launched web_launcher.py with PID: {launcher_process.pid}")

        except Exception as e:
            messages.error(request, f"Failed to launch detection service launcher: {e}")
            print(f"Error launching web_launcher.py: {e}")

    return redirect(redirect_url)


# Ensure prepare_launcher_for_camera is also correctly defined
def prepare_launcher_for_camera(request, camera_pk):
    # 1. Authenticate and get officer/station
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        messages.error(request, "Authentication required.")
        return redirect(reverse('login')) # Ensure 'login' URL name is correct

    login_id = request.session.get('user_id')
    try:
        # Import your models if not already at the top
        from .models import forest_officer, camera 
        current_officer = forest_officer.objects.get(LOGIN__id=login_id)
        officer_station = current_officer.STATION
        cam_to_launch = camera.objects.get(pk=camera_pk, station=officer_station)
    except forest_officer.DoesNotExist:
        messages.error(request, "Officer profile not found.")
        return redirect(reverse('login'))
    except camera.DoesNotExist:
        messages.error(request, "Camera not found or not assigned to your station.")
        return redirect(reverse('forest_officer_home')) # Ensure this URL name is correct
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")
        return redirect(reverse('forest_officer_home'))

    # 2. Call launch_detection_service_launcher (it will set its own messages and redirect if called directly,
    # but here its redirect will be overridden by the one below)
    launch_detection_service_launcher(request) # This function now handles its own messages and redirect (which we override)

    # 3. Construct the URL for Django Detection Center with query parameters
    target_url = f"{reverse('forest_officer_detection_center')}?camera_id_to_prefill={cam_to_launch.id}&mode=live"
    
    return redirect(target_url)

def prepare_launcher_for_report_image(request, report_pk):
    # 1. Authenticate officer (similar to other views)
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        messages.error(request, "Authentication required.")
        return redirect(reverse('login'))

    try:
        report = get_object_or_404(user_upload, pk=report_pk)

        if not report.image or not hasattr(report.image, 'path'):
            messages.error(request, "Report does not have a valid image or image path.")
            return redirect(request.META.get('HTTP_REFERER', reverse('forest_officer_view_user_report')))

        image_file_path = report.image.path
        encoded_image_path = urllib.parse.quote_plus(image_file_path)

    except user_upload.DoesNotExist:
        messages.error(request, "User report not found.")
        return redirect(reverse('forest_officer_view_user_report'))
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")
        return redirect(reverse('forest_officer_view_user_report'))

    target_url = f"{reverse('forest_officer_detection_center')}?camera_id_to_prefill=0&camera_source_default={encoded_image_path}&mode=image"
    image_filename = os.path.basename(image_file_path) if image_file_path else "Unknown Image"
    messages.info(request, f"Preparing to analyze image: {image_filename}. Redirecting to Detection Center.", extra_tags="safe")
    
    return redirect(target_url)


# --- NATIVE DJANGO AI DETECTION CENTER VIEWS ---
django_active_processes = {}

def refresh_django_process_statuses():
    for cam_id in list(django_active_processes.keys()):
        pinfo = django_active_processes[cam_id]
        if pinfo.get('status') == 'running' and 'process' in pinfo:
            if pinfo['process'].poll() is not None:
                pinfo['status'] = 'terminated'

def forest_officer_detection_center(request):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        messages.error(request, "Authentication required.")
        return redirect('login')

    login_id = request.session.get('user_id')
    station_cams = []
    try:
        from .models import forest_officer, camera
        current_officer = forest_officer.objects.get(LOGIN__id=login_id)
        if current_officer.STATION:
            station_cams = camera.objects.filter(station=current_officer.STATION)
    except Exception as e:
        print(f"Error fetching officer cameras: {e}")

    refresh_django_process_statuses()

    prefill_camera_id_str = request.GET.get('camera_id_to_prefill')
    prefill_camera_source_val = request.GET.get('camera_source_default', '')
    req_mode = request.GET.get('mode', '')

    processed_prefill_camera_id = None
    if prefill_camera_id_str:
        try:
            processed_prefill_camera_id = int(prefill_camera_id_str)
        except ValueError:
            pass

    active_mode = req_mode
    if not active_mode:
        if prefill_camera_source_val and any(prefill_camera_source_val.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff']):
            active_mode = 'image'
        else:
            active_mode = 'live'

    context = {
        'station_cameras': station_cams,
        'prefill_camera_id': processed_prefill_camera_id,
        'prefill_camera_source': prefill_camera_source_val,
        'active_mode': active_mode,
        'active_processes': django_active_processes
    }
    return render(request, 'Forest Officer/detection_center.html', context)

def start_detection_process_view(request):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        messages.error(request, "Authentication required.")
        return redirect('login')

    if request.method == 'POST':
        camera_id_str = request.POST.get('camera_id', '0')
        camera_source = request.POST.get('camera_source', '0')
        mode = request.POST.get('mode', 'live')
        mqtt_action = request.POST.get('mqtt_action', 'START')

        # Handle uploaded image if present
        if 'image_file' in request.FILES:
            image_file = request.FILES['image_file']
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
            safe_name = timestamp + image_file.name.replace(' ', '_')
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'User_Uploaded_Analysis')
            os.makedirs(upload_dir, exist_ok=True)
            saved_path = os.path.join(upload_dir, safe_name)
            with open(saved_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)
            camera_source = saved_path

        try:
            camera_id = int(camera_id_str) if camera_id_str else 0
        except ValueError:
            camera_id = 0

        # Also attempt MQTT activation dispatch for remote edge nodes automatically
        try:
            import paho.mqtt.publish as publish
            broker = os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
            port = int(os.getenv("MQTT_BROKER_PORT", 1883))
            topic = f"wildeye/camera/{camera_id}/command"
            payload = json.dumps({"action": "START", "camera_id": camera_id, "timestamp": datetime.now().isoformat()})
            publish.single(topic, payload, hostname=broker, port=port)
            print(f"Dispatched MQTT START to {topic}")
        except Exception as e:
            print(f"MQTT dispatch warning: {e}")

        # Local process launch
        refresh_django_process_statuses()
        if camera_id in django_active_processes and django_active_processes[camera_id].get('status') == 'running':
            messages.error(request, f"Detection process for Camera #{camera_id} is already running (PID: {django_active_processes[camera_id]['pid']}).")
            return redirect('forest_officer_detection_center')

        detection_script = os.path.abspath(os.path.join(settings.BASE_DIR, "..", "edge_node", "animal_using_video.py"))
        if not os.path.exists(detection_script):
            messages.error(request, f"Detection script not found at {detection_script}")
            return redirect('forest_officer_detection_center')

        cmd = [sys.executable, detection_script, '--camera-id', str(camera_id), '--camera-source', camera_source]
        try:
            proc = subprocess.Popen(cmd)
            django_active_processes[camera_id] = {
                'process': proc,
                'pid': proc.pid,
                'source': camera_source,
                'status': 'running'
            }
            messages.success(request, f"Activated AI Detection for Camera #{camera_id} (PID: {proc.pid}).")
        except Exception as e:
            messages.error(request, f"Failed to launch detection process: {e}")

    return redirect('forest_officer_detection_center')

def stop_detection_process_view(request, camera_id):
    if not request.session.get('is_authenticated') or request.session.get('user_type') != 'officer':
        messages.error(request, "Authentication required.")
        return redirect('login')

    refresh_django_process_statuses()
    if camera_id in django_active_processes and django_active_processes[camera_id].get('status') == 'running':
        pinfo = django_active_processes[camera_id]
        try:
            pinfo['process'].terminate()
            try:
                pinfo['process'].wait(timeout=5)
            except subprocess.TimeoutExpired:
                pinfo['process'].kill()
            pinfo['status'] = 'terminated'
            messages.success(request, f"Stopped detection process for Camera #{camera_id} (PID: {pinfo['pid']}).")
        except Exception as e:
            messages.error(request, f"Error stopping process: {e}")
    else:
        messages.info(request, f"No active process found for Camera #{camera_id}.")

    return redirect('forest_officer_detection_center')

def ajax_detection_status(request):
    refresh_django_process_statuses()
    status_list = []
    for cid, data in django_active_processes.items():
        status_list.append({
            'camera_id': cid,
            'pid': data.get('pid'),
            'source': data.get('source'),
            'status': data.get('status')
        })
    return JsonResponse({'processes': status_list})


def check_username_exists_userapp(request):
    """
    Checks if a username is available.
    Can be used for both new user registration and existing user updates.

    Query Parameters:
    - username (required): The username to check.
    - login_id (optional): The ID of the current user, to exclude them from the check
                           during an update operation.
    """
    username = request.GET.get('username', None)

    if not username:
        return JsonResponse({'error': 'Username parameter is missing'}, status=400)

    # Start with a base query for the username (case-insensitive)
    query = RegularUserLogin.objects.filter(username__iexact=username)

    # If a login_id is provided, it means we are in "update" mode.
    # We must exclude the current user from the search, because it's okay for
    # the username to match the current user's own username.
    login_id_to_exclude = request.GET.get('login_id', None)
    if login_id_to_exclude:
        try:
            # Exclude the user who is making the request
            query = query.exclude(id=int(login_id_to_exclude))
        except (ValueError, TypeError):
            # Handle cases where login_id is not a valid integer.
            # You might want to log this error.
            # For safety, we can return a "bad request" response.
            return JsonResponse({'error': 'Invalid login_id format'}, status=400)

    # .exists() will now run on the final, correct query
    is_taken = query.exists()

    # The Android app expects 'is_available', which is the opposite of 'is_taken'
    data = {
        'is_available': not is_taken
    }

    return JsonResponse(data)

def check_email_exists_userapp(request):
    """
    Checks if an email is available.
    Can be used for both new user registration and existing user updates.

    Query Parameters:
    - email (required): The email to check.
    - login_id (optional): The ID of the current user's login, to exclude their
                           own email from the check during an update.
    """
    email = request.GET.get('email', None)

    if not email:
        return JsonResponse({'error': 'Email parameter is missing'}, status=400)

    # Use the model that stores the email field.
    # I'm assuming a UserDetails model. Change it to your actual model.
    # .filter(email__iexact=email) makes the check case-insensitive.
    query = user_table.objects.filter(email__iexact=email)

    login_id_to_exclude = request.GET.get('login_id', None)
    if login_id_to_exclude:
        try:
            # Exclude the user who is making the request.
            # We filter on the 'login' foreign key field.
            query = query.exclude(REGULAR_LOGIN_id=int(login_id_to_exclude))
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid login_id format'}, status=400)

    is_taken = query.exists()

    data = {
        'is_available': not is_taken
    }

    return JsonResponse(data)

def check_phone_exists_userapp(request):
    """
    Checks if a phone number is available.
    Can be used for both new user registration and existing user updates.

    Query Parameters:
    - phone (required): The phone number to check.
    - login_id (optional): The ID of the current user's login, to exclude them from the check.
    """
    phone_number = request.GET.get('phone', None)

    if not phone_number:
        return JsonResponse({'error': 'Phone number parameter is missing'}, status=400)

    # Use the model that stores the phone field.
    # Change 'UserDetails' and the field 'phone' to match your actual model.
    query = user_table.objects.filter(phone=phone_number)

    login_id_to_exclude = request.GET.get('login_id', None)
    if login_id_to_exclude:
        try:
            # Exclude the user who is making the request
            query = query.exclude(REGULAR_LOGIN_id=int(login_id_to_exclude))
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid login_id format'}, status=400)

    is_taken = query.exists()

    data = {
        'is_available': not is_taken
    }

    return JsonResponse(data)