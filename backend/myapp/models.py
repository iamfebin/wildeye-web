from django.db import models
from django.contrib.auth.hashers import make_password, check_password # Import hashing utilities
from django.utils import timezone
import uuid
from datetime import timedelta
import os # Import for token generation
import binascii # Import for token generation
from django.conf import settings

# from django.contrib.gis.db import models

# Create your models here.
class login_table(models.Model):
    username=models.CharField(max_length=100)
    password=models.CharField(max_length=100)
    type=models.CharField(max_length=100)


class forest_division(models.Model):
    name=models.CharField(max_length=100)
    place=models.CharField(max_length=100)

class forest_station(models.Model):
    DIVISION=models.ForeignKey(forest_division, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    place = models.CharField(max_length=100)
    phone = models.BigIntegerField()
    # NEW: Add these fields for map boundary center
    latitude = models.FloatField(null=True, blank=True, help_text="Latitude of the station's center point")
    longitude = models.FloatField(null=True, blank=True, help_text="Longitude of the station's center point")

    def __str__(self):
        return self.name # Or f"{self.name} ({self.place})"



class forest_officer(models.Model):
    LOGIN=models.ForeignKey(login_table, on_delete=models.CASCADE)
    STATION=models.ForeignKey(forest_station, on_delete=models.SET_NULL, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.BigIntegerField()
    email = models.CharField(max_length=100)
    image = models.FileField()
    dob = models.DateField(null=True)
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"





# NEW: DangerousArea Model
class DangerousArea(models.Model):
    """
    Represents a dangerous area marked on the map.
    Stores GeoJSON data for the polygon and is linked to a specific forest station.
    """
    # models.JSONField is available in Django 3.1+ and works with MySQL 5.7.8+
    # If using older versions, you'd need models.TextField and manual JSON serialization/deserialization.
    geojson_data = models.JSONField(
        help_text="GeoJSON representation of the dangerous area polygon."
    )
    station = models.ForeignKey(
        forest_station,
        on_delete=models.CASCADE,
        related_name='dangerous_areas',
        help_text="The forest station/area this dangerous zone belongs to."
    )
    # Link to your custom forest_officer model
    created_by_officer = models.ForeignKey(
        forest_officer,
        on_delete=models.SET_NULL, # If officer is deleted, set this to NULL
        null=True,
        blank=True,
        related_name='created_dangerous_areas',
        help_text="The forest officer who created this dangerous area."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dangerous Area"
        verbose_name_plural = "Dangerous Areas"

    def __str__(self):
        return f"Dangerous Area near {self.station.name} (ID: {self.id})"







# New model for Hashed Regular User Logins
class RegularUserLogin(models.Model):
    username = models.CharField(max_length=100, unique=True) # Ensure unique usernames
    password = models.CharField(max_length=128) # CharField size recommended for hashed passwords

    def set_password(self, raw_password):
        # Hash the password before saving
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        # Check a raw password against the hashed password
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.username

# Link your user_table to this new hashed login table
class user_table(models.Model): 
    REGULAR_LOGIN = models.OneToOneField(RegularUserLogin, on_delete=models.CASCADE, null=True)
    STATION = models.ForeignKey(forest_station, on_delete=models.SET_NULL, null=True, blank=True) # Link user to a station
    first_name = models.CharField(max_length=90)
    last_name = models.CharField(max_length=100)
    place = models.CharField(max_length=100)
    pin = models.BigIntegerField()
    phone = models.BigIntegerField(db_index=True)
    email = models.CharField(max_length=100, db_index=True)
    image = models.FileField(null=True, blank=True, upload_to='user_images/') # Add upload_to

    def __str__(self):
        return f"{self.first_name} {self.last_name}"




class contacts(models.Model):
    name = models.CharField(max_length=100)
    details = models.TextField()
    phone = models.BigIntegerField()

class feedback_table(models.Model):
    USER = models.ForeignKey(user_table, on_delete=models.CASCADE)
    details = models.TextField()
    date = models.DateField(auto_now_add=True) # Automatically set date when feedback is created

class complaints(models.Model):
    USER = models.ForeignKey(user_table, on_delete=models.CASCADE)
    STATION = models.ForeignKey(forest_station, on_delete=models.SET_NULL, null=True, blank=True) # NEW: Link to forest station
    complaint = models.TextField()
    contact_number = models.BigIntegerField(null=True, blank=True) # NEW: Contact number for the complaint
    timestamp = models.DateTimeField(auto_now_add=True) # Automatically sets the timestamp when created
    reply = models.CharField(max_length=100, blank=True, default="") # Allow empty reply and set default
    # date = models.CharField(max_length=100)
    def __str__(self):
        return f"Complaint by {self.USER.first_name} for {self.STATION.name if self.STATION else 'N/A Station'} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class admin_notification(models.Model):
    notification = models.FileField()
    display_name = models.CharField(max_length=255, blank=True, null=True, help_text="Optional: A custom name for this notification file.") # New field
    date = models.DateField()
    time = models.TimeField(auto_now_add=True) # Saves time when object is first created

    def __str__(self):
        # Use display_name if available, otherwise part of the filename
        name_part = self.display_name if self.display_name else self.notification.name.split('/')[-1]
        return f"Notification '{name_part}' on {self.date} at {self.time}"

class daily_reports(models.Model):
    OFFICER = models.ForeignKey(forest_officer, on_delete=models.CASCADE)
    report = models.FileField()
    date = models.DateField()



class animal(models.Model):
    name = models.CharField(max_length=100, unique=True) # Making name unique is good practice
    details = models.TextField()
    image = models.FileField(null=True, blank=True, upload_to='animal_images/') # Specify an upload_to path
    type = models.CharField(max_length=100, null=True)
    is_core_animal = models.BooleanField(default=False, help_text="Core animals cannot be deleted and their names cannot be changed.")

    def __str__(self):
        return self.name

    # Optional: Method to handle image deletion when animal record is deleted
    # This is already handled in your view, but can also be done via signals
    def delete(self, *args, **kwargs):
        if self.image:
            image_path = os.path.join(settings.MEDIA_ROOT, str(self.image))
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"Error deleting image file {self.image.name} during model delete: {e}")
        super().delete(*args, **kwargs)


# class animal(models.Model):
#     name = models.CharField(max_length=100)
#     details = models.TextField()
#     image = models.FileField(null=True, blank=True)
#     type = models.CharField(max_length=100, null=True)
#     def __str__(self):
#         return self.name # This tells Django to use the 'name' field as the string representation


class camera(models.Model):
    camera_id = models.BigIntegerField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    # Add this ForeignKey field to link camera to a forest station
    station = models.ForeignKey(forest_station, on_delete=models.CASCADE, null=True, blank=True) # Using null=True, blank=True initially for easier migration if you have existing data

    def __str__(self):
        return f"Camera {self.camera_id} ({self.station.name if self.station else 'Unassigned'})"


class dangerous_spot(models.Model):
    name = models.CharField(max_length=200)
    latitude = models.FloatField()
    longitude = models.FloatField()
    date = models.DateField()
    # Use a GeometryField to store the drawn shape
    # This can hold Point, Polygon, Rectangle (as Polygon), Circle (as Polygon), etc.
    #geometry = models.GeometryField()

    # def __str__(self):
    #     return self.name
    #
    # # Optional: Add a property to easily get GeoJSON for the frontend
    # @property
    # def geojson_feature(self):
    #     # Returns a GeoJSON Feature dictionary
    #     return {
    #         "type": "Feature",
    #         "properties": {
    #             "id": self.id, # Include ID for frontend editing/deleting
    #             "name": self.name,
    #             "date": self.date.strftime('%Y-%m-%d'), # Format date
    #             # Add other attributes if needed
    #         },
    #         "geometry": self.geometry.geojson # Get the GeoJSON geometry string
    #     }

# Note: After changing the model, you will need to run
# python manage.py makemigrations your_app_name
# python manage.py migrate
# This will create or alter the table to include the spatial column.
# If you have existing data with lat/lng, you'll need a data migration
# to convert it, or you might just clear the table for this new approach.

class camera_alerts(models.Model):
    CAMERA = models.ForeignKey(camera, on_delete=models.CASCADE)
    ANIMAL = models.ForeignKey(animal, on_delete=models.CASCADE)
    image = models.FileField()
    date = models.DateField(db_index=True)
    time = models.TimeField()
    # Add created_at for better filtering in API
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    def __str__(self):
        # This method determines how the object is represented as a string
        # Include key information to identify the alert
        # Make sure CAMERA, ANIMAL, date, and time fields exist in your camera_alerts model
        camera_id = self.CAMERA.id if self.CAMERA else 'N/A Camera'
        animal_name = self.ANIMAL.name if self.ANIMAL else 'Unknown Animal'
        alert_date = self.date.strftime('%Y-%m-%d') if self.date else 'N/A Date'
        alert_time = self.time.strftime('%H:%M') if self.time else 'N/A Time'


        return f"Alert: {animal_name} at Camera {camera_id} on {alert_date} {alert_time}"



class user_upload(models.Model):
    STATUS_CHOICES = [
        ('verified', 'Verified'),
        ('pending_investigation', 'Pending Investigation'),
        ('inconclusive', 'Inconclusive'),
    ]
    USER = models.ForeignKey(user_table, on_delete=models.CASCADE)
    # --- New field to link to ForestStation ---
    station = models.ForeignKey(forest_station, on_delete=models.SET_NULL, null=True, blank=True)
    # Using models.SET_NULL means if a station is deleted, this field becomes NULL.
    # null=True, blank=True allows sightings to be reported without being linked to a station initially.
    # --- End new field ---

    image = models.FileField(null=True, blank=True, upload_to='user_sighting_images/')
    animal = models.CharField(max_length=50)
    latitude = models.BigIntegerField(null=True, blank=True)
    longitude = models.BigIntegerField(null=True, blank=True)
    animal_type = models.CharField(max_length=50) #carnivores,herbivores, etc
    date = models.DateField(null=True, blank=True, db_index=True)
    time = models.TimeField(null=True, blank=True)
    location_details = models.CharField(max_length=100)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending_investigation',
        db_index=True
    )
    def __str__(self):
        # Ensure USER.first_name/id can be accessed, handle potential None if user_table was deleted
        user_info = f"User {self.USER.id}" if self.USER else "Unknown User"
        return f"Report by {user_info} on {self.date}"
    # def __str__(self):
    #     return f"Report by {self.USER.first_name} on {self.date}"

class SightingLike(models.Model):
    sighting = models.ForeignKey('user_upload', related_name='likes', on_delete=models.CASCADE)
    user = models.ForeignKey('RegularUserLogin', related_name='sighting_likes', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures a user can only like a specific sighting once
        unique_together = ('sighting', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} likes sighting ID {self.sighting.id}"



class curfew_info(models.Model):
    # Define choices for threat_level
    THREAT_LEVEL_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]

    OFFICER = models.ForeignKey(forest_officer, on_delete=models.CASCADE)
    curfew_name = models.CharField(max_length=50)
    curfew_details = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField()
    end_date = models.DateField()
    affected_area = models.CharField(max_length=100)
    # Use choices for threat_level
    threat_level = models.CharField(
        max_length=50,
        choices=THREAT_LEVEL_CHOICES,
        default='Unknown' # Optional: set a default value
    )
    def __str__(self):
        return self.curfew_name


class trekking(models.Model):
    USER = models.ForeignKey(user_table, on_delete=models.CASCADE)
    Trekking_area = models.CharField(max_length=50)
    No_of_trekkers = models.IntegerField()
    Purpose_of_trek = models.CharField(max_length=100)
    Emergency_contact_no = models.BigIntegerField()
    Requested_date = models.DateField()
    Requested_time = models.TimeField()
    ID_proof = models.FileField()

class alert_to_user(models.Model):
    TARGET_CHOICES = [
        ('ALL', 'All Users'),
        ('OWN_STATION', "Users Near Officer's Own Station"),
    ]
    CAMERA_ALERT = models.ForeignKey(camera_alerts, on_delete=models.CASCADE)
    OFFICER = models.ForeignKey(forest_officer, on_delete=models.CASCADE)
    affected_area = models.CharField(max_length=100)
    threat_level = models.CharField(max_length=100)
    action_to_take = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True) # Add timestamp for ordering/filtering
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default='ALL')
    target_station = models.ForeignKey(forest_station, on_delete=models.SET_NULL, null=True, blank=True) # Which station if target is NEAR_STATION
        # Add the 'is_seen' field here with a default value
    is_seen = models.BooleanField(default=False, db_index=True) # This will provide a value during inserts

    # ---- New fields to store camera location ----
    camera_latitude = models.FloatField(null=True, blank=True)
    camera_longitude = models.FloatField(null=True, blank=True)
    # ---------------------------------------------


    # def __str__(self):
    #     lat_str = f"{self.camera_latitude:.4f}" if self.camera_latitude is not None else "N/A Lat"
    #     lon_str = f"{self.camera_longitude:.4f}" if self.camera_longitude is not None else "N/A Lon"
    #     return f"User Alert: {self.affected_area} ({self.threat_level}) from CamLoc: ({lat_str}, {lon_str})"
    def __str__(self):
        target_desc = "All Users"
        if self.target_audience == 'OWN_STATION':
            target_desc = f"Users of Station: {self.target_station.name if self.target_station else 'Officer Station'}"
        return f"Alert: {self.affected_area} ({self.threat_level}) for {target_desc}"




class TechSupportRequest(models.Model):
    OFFICER = models.ForeignKey(forest_officer, on_delete=models.CASCADE)
    issue_type = models.CharField(
        max_length=50,
        choices=[
            ('detection_system', 'Detection System'),
            ('camera', 'Camera Hardware/Feed'),
            ('network', 'Network Connectivity'),
            ('account', 'Account or Website Problem'),
            ('other', 'Other')
        ]
    )
    description = models.TextField()
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'Pending'),
            ('dispatched', 'Tech Support Person Dispatched'),
            ('resolved', 'Resolved')
        ],
        default='pending'
    )
    resolution_notes = models.TextField(blank=True, null=True)
    resolved_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Tech Support Request by {self.OFFICER.first_name} {self.OFFICER.last_name} - {self.issue_type} ({self.status})"
    

# New Safety Tip models--------------------------

class SafetyTip(models.Model):

    """
    Represents a single safety tip, which can be either an image gallery
    or a PDF document.
    """
    CONTENT_TYPE_CHOICES = [
        ('image_gallery', 'Image Gallery'),
        ('pdf_document', 'PDF Document'),
    ]

    title = models.CharField(max_length=200, help_text="Title of the safety tip (e.g., 'Bear Encounter Safety')")
    thumbnail = models.ImageField(upload_to='thumbnails/', help_text="Thumbnail image for the tip's card display")
    description = models.TextField(blank=True, help_text="Optional: A brief summary of the tip.")
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        default='image_gallery',
        help_text="Choose whether this tip is an image gallery or a PDF document."
    )
    pdf_file = models.FileField(
        upload_to='pdfs/',
        blank=True,
        null=True,
        help_text="Upload a PDF file if 'PDF Document' is selected. Leave blank for image galleries."
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional: Category for filtering (e.g., 'Animal Encounters', 'Survival', 'First Aid')."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Safety Tip"
        verbose_name_plural = "Safety Tips"
        ordering = ['title']

class SafetyTipImage(models.Model):
    """
    Represents an image within an 'Image Gallery' type safety tip.
    """

    safety_tip = models.ForeignKey(
        SafetyTip,
        related_name='images', # This name is used for reverse relation (e.g., tip.images.all())
        on_delete=models.CASCADE,
        limit_choices_to={'content_type': 'image_gallery'}, # Only link to image galleries
        help_text="Select the Safety Tip (must be an Image Gallery type) this image belongs to."
    )
    image = models.ImageField(upload_to='tip_images/', help_text="Upload an image for this gallery.")
    caption = models.TextField(blank=True, help_text="Optional: Caption for the image.")
    order = models.PositiveIntegerField(default=0, help_text="Order of the image in the gallery.")

    class Meta:
        ordering = ['order']
        verbose_name = "Safety Tip Image"
        verbose_name_plural = "Safety Tip Images"

    def __str__(self):
        return f"Image for {self.safety_tip.title} (Order: {self.order})"
    
    # NEW: Trekking Request Model
class TrekkingRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(user_table, on_delete=models.CASCADE, related_name='trekking_requests')
    # Denormalized user info for easier access/history, could be populated from user_table
    full_name = models.CharField(max_length=200)
    phone = models.BigIntegerField()
    email = models.CharField(max_length=100)
    id_card_pdf = models.FileField(upload_to='trekking_id_cards/', help_text="PDF of user's ID card")
    
    trekkers_count = models.IntegerField(default=1, help_text="Number of people in the trekking group")
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    destination = models.CharField(max_length=255, help_text="Specific area or route for trekking")
    purpose = models.TextField(blank=True, help_text="Brief purpose of the trekking")

    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True)

    reviewed_by_officer = models.ForeignKey(forest_officer, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_trekking_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    officer_notes = models.TextField(blank=True, help_text="Notes from the reviewing officer")
    station = models.ForeignKey(forest_station, on_delete=models.SET_NULL, null=True, blank=True, related_name='trekking_requests')

    def __str__(self):
        return f"Trekking Request by {self.full_name} ({self.status}) on {self.requested_at.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-requested_at'] # Order by most recent requests first


# NEW: Trekking Pass Model
class TrekkingPass(models.Model):
    request = models.OneToOneField(TrekkingRequest, on_delete=models.CASCADE, related_name='trekking_pass')
    issued_by = models.ForeignKey(forest_officer, on_delete=models.SET_NULL, null=True, related_name='issued_trekking_passes')
    
    # Validity period for the pass
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    
    instructions = models.TextField(help_text="Instructions/conditions for the trekking pass")
    pass_pdf = models.FileField(upload_to='trekking_passes/', null=True, blank=True, help_text="Generated PDF of the trekking pass")
    
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trekking Pass for {self.request.full_name} (Req ID: {self.request.id})"

    class Meta:
        ordering = ['-issued_at']


# --- NEW MODEL FOR USER PASSWORD RESET TOKENS ---
class PasswordResetToken(models.Model):
    user = models.ForeignKey(RegularUserLogin, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True) # A unique token for reset
    created_at = models.DateTimeField(auto_now_add=True)
    # Token valid for 1 hour (adjust as needed)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.id: # Only generate token and expiry on creation
            self.token = self.generate_token()
            self.expires_at = timezone.now() + timezone.timedelta(hours=1) # Token valid for 1 hour
        super().save(*args, **kwargs)

    def generate_token(self):
        # Generate a random, cryptographically secure token
        return binascii.hexlify(os.urandom(32)).decode() # 64 characters long

    def is_valid(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return f"Token for {self.user.username} (Expires: {self.expires_at})"        


# Officer Password Reset-----

class OfficerPasswordResetToken(models.Model):
    officer = models.ForeignKey('forest_officer', on_delete=models.CASCADE) # Use string 'forest_officer' if defined later
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.pk: # Only set expires_at on creation
            self.expires_at = timezone.now() + timedelta(hours=1) # Token expires in 1 hour
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Token for {self.officer.first_name} {self.officer.last_name}"