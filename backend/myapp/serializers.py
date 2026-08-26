# your_app_name/serializers.py
import base64 # Import base64 for PDF decoding
from django.core.files.base import ContentFile # Import ContentFile for creating file from bytes
from rest_framework import serializers
from .models import alert_to_user, camera_alerts, camera, animal, forest_station, user_table, complaints, forest_officer, login_table, RegularUserLogin, DangerousArea, TrekkingRequest, TrekkingPass, contacts # Import all necessary models
from drf_extra_fields.fields import Base64ImageField # Or drf_base64.fields.Base64ImageField

# Serializer for the nested camera_alerts object
class CameraAlertSerializer(serializers.ModelSerializer):
    """
    Serializer for the camera_alerts model.
    Defines how camera_alerts data is represented in JSON.
    """
    animal_name = serializers.CharField(source='ANIMAL.name', read_only=True)


    class Meta:
        model = camera_alerts
        fields = [
            'id',           # Primary key of the camera_alerts object
            'CAMERA',       # ForeignKey to Camera model (will include ID by default)
            'ANIMAL',       # ForeignKey to Animal model (will include ID by default)
            'animal_name',
            'image',        # FileField for the image (will be relative path)
            'date',         # DateField
            'time',         # TimeField
            'created_at',   # DateTimeField
            # Include any other fields from your camera_alerts model here
        ]

class CameraMapSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True, default='Unassigned')
    
    class Meta:
        model = camera
        fields = ['id', 'camera_id', 'latitude', 'longitude', 'station', 'station_name']

class CameraAlertMapSerializer(serializers.ModelSerializer):
    animal_name = serializers.CharField(source='ANIMAL.name', read_only=True, default='Unknown Wildlife')
    camera_number = serializers.IntegerField(source='CAMERA.camera_id', read_only=True)
    latitude = serializers.FloatField(source='CAMERA.latitude', read_only=True)
    longitude = serializers.FloatField(source='CAMERA.longitude', read_only=True)
    station_name = serializers.CharField(source='CAMERA.station.name', read_only=True, default='N/A')
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = camera_alerts
        fields = ['id', 'camera_number', 'latitude', 'longitude', 'animal_name', 'image', 'image_url', 'date', 'time', 'created_at', 'station_name']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

# Serializer for the alert_to_user object, including the nested camera_alerts
class AlertSerializer(serializers.ModelSerializer):
    """
    Serializer for the alert_to_user model, with nested camera_alerts data.
    """
    # This line tells DRF to use the CameraAlertSerializer to serialize
    # the related CAMERA_ALERT object and include it as a nested JSON object.
    CAMERA_ALERT = CameraAlertSerializer(read_only=True)

    class Meta:
        model = alert_to_user
        fields = [
            'id',
            'CAMERA_ALERT', # Include the nested camera alert data using the defined field above
            'affected_area',
            'threat_level',
            'action_to_take',
            'created_at',
            'target_audience',
            'is_seen',
            'camera_latitude',
            'camera_longitude'
            # Include any other fields from alert_to_user you need
        ]



class ForestStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = forest_station
        fields = ['id', 'name', 'place', 'phone', 'latitude', 'longitude'] # <--- UPDATED THIS LINE

class UserRegistrationSerializer(serializers.ModelSerializer):
    profile_image = Base64ImageField(required=False, allow_null=True) # New field

    class Meta:
        model = user_table  # Your User model
        fields = ['username', 'password', 'first_name', 'last_name', 'place',
                  'pin', 'phone', 'email', 'profile_image']
        extra_kwargs = {'password': {'write_only': True}}


# NEW: Serializer for ForestOfficer to get specific details
class ForestOfficerSerializer(serializers.ModelSerializer):
    # This will return the full name of the officer
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = forest_officer
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'full_name'] # Add fields you want to expose

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

# NEW: Serializer for Complaint Submission (less detailed, mainly for creating)
class ComplaintSerializer(serializers.ModelSerializer):
    class Meta:
        model = complaints
        fields = ['id', 'USER', 'STATION', 'complaint', 'contact_number', 'timestamp', 'reply'] # 'reply' will be empty on submission
        read_only_fields = ['timestamp', 'reply'] # User cannot set reply, it's set by officer




from .spatial_utils import validate_geojson_geometry

class DangerousAreaSerializer(serializers.ModelSerializer):
    """
    Serializer for the DangerousArea model.
    Includes the ID, GeoJSON data, station name, and creator officer's username.
    """
    # Read-only field to display the station name
    station_name = serializers.CharField(source='station.name', read_only=True)
    # Read-only field to display the username of the officer who created it
    created_by_officer_username = serializers.CharField(source='created_by_officer.username', read_only=True)

    # This field is used for writing (creating/updating) by accepting the station's primary key (ID)
    station_id = serializers.PrimaryKeyRelatedField(
        queryset=forest_station.objects.all(), source='station', write_only=True
    )

    class Meta:
        model = DangerousArea
        # Include 'station_id' for input, but display 'station_name' and 'station' for output
        # 'created_by_officer' is set automatically by the view, so it's read-only here
        fields = [
            'id', 'geojson_data', 'station', 'station_id', 'station_name',
            'created_by_officer', 'created_by_officer_username', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'station', 'created_by_officer']

    def validate_geojson_data(self, value):
        """
        Validate that geojson_data is a valid, closed, non-self-intersecting GeoJSON Polygon.
        """
        is_valid, err_or_shape = validate_geojson_geometry(value)
        if not is_valid:
            raise serializers.ValidationError(f"Invalid polygon geometry: {err_or_shape}")
        return value



# NEW: Trekking Pass Serializer
class TrekkingPassSerializer(serializers.ModelSerializer):
    request_id = serializers.IntegerField(source='request.id', read_only=True)
    user_full_name = serializers.CharField(source='request.user.first_name', read_only=True) # Adjust to your user's name fields
    issued_by_officer_name = serializers.SerializerMethodField(read_only=True)
    pass_pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = TrekkingPass
        fields = [
            'id', 'request', 'request_id', 'user_full_name',
            'issued_by', 'issued_by_officer_name', 'valid_from', 'valid_to',
            'instructions', 'pass_pdf', 'pass_pdf_url', 'issued_at'
        ]
        read_only_fields = ('issued_at', 'pass_pdf') # pass_pdf is generated by backend

    def get_issued_by_officer_name(self, obj):
        if obj.issued_by:
            return f"{obj.issued_by.first_name} {obj.issued_by.last_name}"
        return None

    def get_pass_pdf_url(self, obj):
        if obj.pass_pdf:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.pass_pdf.url)
        return None

class TrekkingRequestSerializer(serializers.ModelSerializer):
    # The 'user' field is a ForeignKey to user_table.
    # We set this field in perform_create, so it should not be required from the client.
    # Make it read-only. The client should NOT send 'user' or 'user_id' in the request body.
    # The 'user_id' sent from the Android app is handled separately in the view's logic.
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    # Add fields for display purposes that are derived from related models
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    reviewed_by_officer_name = serializers.CharField(source='reviewed_by_officer.LOGIN.username', read_only=True)

    # Nested serializer for TrekkingPass, read-only as it's created/updated by the officer review
    trekking_pass = TrekkingPassSerializer(read_only=True)

    # For station name (read-only display). This will display the station's name.
    station_name = serializers.SerializerMethodField()
    # For accepting station_id during creation. This field is write-only.
    # It will be used in the create method to find the actual ForestStation instance.
    station_id = serializers.IntegerField(write_only=True, required=True)

    # NEW: Fields to receive base64 encoded PDF data and its filename
    # These are write-only as they are for input, not output.
    # They are not directly mapped to a model field but processed in create().
    id_card_pdf_base64 = serializers.CharField(write_only=True, required=False, allow_null=True)
    id_card_pdf_filename = serializers.CharField(write_only=True, required=False, allow_null=True)


    class Meta:
        model = TrekkingRequest
        fields = [
            'id', 'user', 'user_full_name', 'user_last_name',
            'full_name', 'phone', 'email',
            'trekkers_count',
            'start_date', 'end_date', 'start_time', 'end_time', 'destination',
            'purpose', 'requested_at', 'status', 'reviewed_by_officer',
            'reviewed_by_officer_name', 'reviewed_at', 'officer_notes', 'trekking_pass',
            'station', 'station_name', 'station_id',
            'id_card_pdf_base64', 'id_card_pdf_filename'
        ]
        # Mark all fields that are set by the backend or are derived as read-only.
        # This prevents them from being required or writable by the client.
        read_only_fields = [
            'user', 'user_full_name', 'user_last_name', 'requested_at',
            'status', 'reviewed_by_officer', 'reviewed_by_officer_name',
            'reviewed_at', 'officer_notes', 'trekking_pass',
            'full_name', 'phone', 'email', 'station', 'station_name',
            'id_card_pdf' 
        ]

    # Method to get the station name for display
    def get_station_name(self, obj):
        return obj.station.name if obj.station else None

    def create(self, validated_data):
        # The 'user' object is passed by the ViewSet's perform_create method
        user_profile = validated_data.pop('user')

        # Get station_id from validated_data (which comes from the write_only field)
        station_id = validated_data.pop('station_id')
        try:
            station_instance = forest_station.objects.get(id=station_id)
        except forest_station.DoesNotExist:
            raise serializers.ValidationError({"station_id": "Invalid forest station ID."})

        # NEW: Handle base64 PDF from validated_data
        id_card_pdf_base64 = validated_data.pop('id_card_pdf_base64', None)
        id_card_pdf_filename = validated_data.pop('id_card_pdf_filename', None)

        if id_card_pdf_base64 and id_card_pdf_filename:
            try:
                file_data = base64.b64decode(id_card_pdf_base64)
                pdf_file = ContentFile(file_data, name=id_card_pdf_filename)
                validated_data['id_card_pdf'] = pdf_file # Assign the ContentFile to the model's FileField
            except Exception as e:
                raise serializers.ValidationError({"id_card_pdf_base64": f"Invalid PDF data: {e}"})
        else:
            # If PDF is required, raise an error. Otherwise, it can be null.
            # Based on your Android code, it seems to be required.
            raise serializers.ValidationError({"id_card_pdf": "ID Card PDF is required."})


        # Populate denormalized fields from the user_profile
        validated_data['full_name'] = f"{user_profile.first_name} {user_profile.last_name}"
        validated_data['phone'] = user_profile.phone
        validated_data['email'] = user_profile.email

        # Create the TrekkingRequest instance, passing user and station instances
        trekking_request = TrekkingRequest.objects.create(
            user=user_profile,
            station=station_instance, # Assign the fetched station instance
            **validated_data
        )
        return trekking_request


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = contacts
        fields = ['id', 'name', 'details', 'phone'] # Or '__all__' if you want all field







