from django import forms
from .models import camera_alerts, animal, camera, curfew_info, user_upload, complaints, alert_to_user, forest_station, forest_officer



class CameraAlertForm(forms.ModelForm):
    class Meta:
        model = camera_alerts
        # Let the ModelForm handle the fields automatically
        fields = '__all__'
        # OR list them explicitly:
        # fields = ['CAMERA', 'ANIMAL', 'image', 'date', 'time']

    # You can remove the label_from_instance method now
    # def label_from_instance(self, obj):
    #     ...

class CameraAlertEditForm(forms.ModelForm):
    CAMERA = forms.ModelChoiceField(
        queryset=camera.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label="Associated Camera"
    )
    ANIMAL = forms.ModelChoiceField(
        queryset=animal.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label="Detected Animal"
    )
    # Use forms.FileInput instead of ClearableFileInput
    image = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control form-control-lg'}), # Standard file input
        required=False, # Image might not be mandatory or already exists
        label="Alert Image (Upload new to replace)"
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control form-control-lg flatpickr-date', 'autocomplete': 'off'}),
        label="Detection Date"
    )
    time = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control form-control-lg flatpickr-time', 'autocomplete': 'off'}),
        label="Detection Time"
    )

    class Meta:
        model = camera_alerts
        fields = ['CAMERA', 'ANIMAL', 'image', 'date', 'time']

    def __init__(self, *args, **kwargs):
        officer_station = kwargs.pop('officer_station', None)
        super().__init__(*args, **kwargs)

        if officer_station:
            self.fields['CAMERA'].queryset = camera.objects.filter(station=officer_station).order_by('camera_id')
        else:
            if self.instance and self.instance.pk and self.instance.CAMERA:
                self.fields['CAMERA'].queryset = camera.objects.filter(pk=self.instance.CAMERA.pk) | \
                                                 (camera.objects.none()) # Fallback to none if no station
                self.fields['CAMERA'].queryset = self.fields['CAMERA'].queryset.distinct()
            else:
                 self.fields['CAMERA'].queryset = camera.objects.none()

        # Display current image path using help_text
        if self.instance and self.instance.pk and self.instance.image and hasattr(self.instance.image, 'url'):
            self.fields['image'].help_text = f"""
                <div class="mt-2">
                    <small class="text-muted">Current image:</small><br>
                    <a href="{self.instance.image.url}" target="_blank">
                        <img src="{self.instance.image.url}" alt="Current Alert Image" style="max-height: 100px; max-width: 150px; border-radius: 0.25rem; border: 1px solid #ddd;">
                    </a>
                </div>
            """
        else:
            self.fields['image'].help_text = "<small class='text-muted'>Upload an image if available. Uploading a new image will replace the current one (if any).</small>"




class CurfewInfoForm(forms.ModelForm):
    curfew_name = forms.CharField(
        label="Curfew Name/Title",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g., Evening Curfew for Sector B', 'maxlength': 50})
    )
    curfew_details = forms.CharField(
        label="Curfew Details/Reason",
        widget=forms.Textarea(attrs={'class': 'form-control form-control-lg', 'rows': 3, 'placeholder': 'Provide specific reasons or instructions for the curfew (max 100 words)', 'maxlength': 100})
    )
    affected_area = forms.CharField(
        label="Affected Area(s)",
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-lg',
            'rows': 3,
            'placeholder': "Clearly define the geographical boundaries or specific areas covered by the curfew in 100 words or less...",
            'maxlength': 100
        })
    )
    start_date = forms.DateField(
        label="Start Date",
        widget=forms.DateInput(attrs={'class': 'form-control form-control-lg flatpickr-date', 'placeholder': 'YYYY-MM-DD', 'autocomplete': 'off'}) # Added form-control-lg
    )
    end_date = forms.DateField(
        label="End Date",
        widget=forms.DateInput(attrs={'class': 'form-control form-control-lg flatpickr-date', 'placeholder': 'YYYY-MM-DD', 'autocomplete': 'off'}) # Added form-control-lg
    )
    start_time = forms.TimeField(
        label="Start Time",
        widget=forms.TimeInput(attrs={'class': 'form-control form-control-lg flatpickr-time', 'placeholder': 'HH:MM', 'autocomplete': 'off'}) # Added form-control-lg
    )
    end_time = forms.TimeField(
        label="End Time",
        widget=forms.TimeInput(attrs={'class': 'form-control form-control-lg flatpickr-time', 'placeholder': 'HH:MM', 'autocomplete': 'off'}) # Added form-control-lg
    )

    class Meta:
        model = curfew_info
        fields = ['curfew_name', 'curfew_details', 'start_date', 'start_time', 'end_date', 'end_time', 'affected_area', 'threat_level']
        widgets = {
            'threat_level': forms.Select(attrs={'class': 'form-select form-select-lg'}),
        }



class UserUploadForm(forms.ModelForm):
    ANIMAL_TYPE_CHOICES = [
        ('', 'Select Animal Type...'), # Added a placeholder
        ('Carnivore', 'Carnivore'),
        ('Herbivore', 'Herbivore'),
        ('Omnivore', 'Omnivore'),
    ]

    animal = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Tiger, Elephant'}),
        label="Animal Name / Species"
    )
    animal_type = forms.ChoiceField(
        choices=ANIMAL_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Animal Type"
    )
    latitude = forms.FloatField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_latitude', 'readonly': 'readonly', 'placeholder': 'Selected on map'}),
        label="Latitude"
    )
    longitude = forms.FloatField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_longitude', 'readonly': 'readonly', 'placeholder': 'Selected on map'}),
        label="Longitude"
    )
    location_details = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g., Near the old watchtower, by the river bend'}),
        label="Additional Location Details",
        required=False
    )
    # Ensure your model's status field has choices defined for the Select widget to populate correctly
    status = forms.ChoiceField( # Or ModelChoiceField if status is a ForeignKey
        choices=user_upload.STATUS_CHOICES, # Example if status has choices
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Report Status"
    )

    class Meta:
        model = user_upload # Replace with your actual model name
        fields = ['animal', 'animal_type', 'latitude', 'longitude', 'location_details', 'status']

  

class ComplaintReplyForm(forms.ModelForm):
    reply = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Type your reply here...',
            'class': 'form-control form-control-lg'  # Added Bootstrap class
        }),
        required=True, # Typically a reply should be required when submitting
        label="Your Reply"
    )

    class Meta:
        model = complaints # Make sure 'complaints' is your actual model name
        fields = ['reply'] # Only allow editing the 'reply' field


class ComplaintFilterForm(forms.Form):
    search_query = forms.CharField(
        label="Search by Keyword",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm', 
            'placeholder': 'Username, name, complaint text, contact, reply...'
        })
    )


class AlertToUserForm(forms.ModelForm):
    THREAT_LEVEL_CHOICES = [
        ('', '---------'), # Optional: Add a blank/placeholder choice
        ('High', 'High'),
        ('Medium', 'Medium'),
        ('Low', 'Low'),
    ]

    CAMERA_ALERT = forms.ModelChoiceField(
        queryset=camera_alerts.objects.none(),  # Initial empty queryset
        label="Select Associated Camera Alert",
        required=True, # Making it optional as per user flow, an officer might create an alert not tied to a specific camera event
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    affected_area = forms.CharField(
        label="Affected Area Description",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g., Near Riverbend, Sector 5 residential area', 'maxlength': 100})
    )
    # Override threat_level to use a ChoiceField
    threat_level = forms.ChoiceField(
        choices=THREAT_LEVEL_CHOICES,
        label="Threat Level",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    action_to_take = forms.CharField(
        label="Recommended Action for Users",
        widget=forms.Textarea(attrs={'class': 'form-control form-control-lg', 'rows': 3, 'placeholder': 'e.g., Avoid the area, Stay indoors after 6 PM (max 100 characters)', 'maxlength': 100 # Add this line to restrict input
        })
    )
    # target_audience choices will come from the model definition.
    # We specify the widget if we want to ensure it's RadioSelect and apply Bootstrap styling.
    target_audience = forms.ChoiceField(
        # choices are automatically populated from the model if not overridden here explicitly
        widget=forms.RadioSelect(attrs={'class': 'form-check-input-radio-group'}), # Custom class for potential JS/CSS hook
        label="Target Audience"
    )


    class Meta:
        model = alert_to_user
        # 'target_station' is handled in the view based on officer or target_audience
        fields = ['CAMERA_ALERT', 'affected_area', 'threat_level', 'action_to_take', 'target_audience']
        # Removed widgets dict from Meta as we are defining widgets directly on fields


    def __init__(self, *args, **kwargs):
        officer_station = kwargs.pop('officer_station', None)
        super().__init__(*args, **kwargs)

        if officer_station:
            self.fields['CAMERA_ALERT'].queryset = camera_alerts.objects.filter(
                CAMERA__station=officer_station,
                # Add any other relevant filters for camera alerts, e.g., recent, unaddressed
            ).select_related('CAMERA').order_by('-date', '-time')
        else:
            # If no officer_station, perhaps allow selection from all alerts or keep it none
            # For now, keeping it as none, but you might want to adjust this logic.
            self.fields['CAMERA_ALERT'].queryset = camera_alerts.objects.none()

        # Dynamically set choices for target_audience from the model to ensure they are current
        self.fields['target_audience'].choices = alert_to_user.TARGET_CHOICES




class CameraForm(forms.ModelForm):
    camera_id = forms.IntegerField(
        label="Camera Device ID (Unique per Station)", # Updated label
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter unique numeric device ID for this station'
        }),
        required=True
    )
    latitude = forms.FloatField(
        label="Latitude",
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'id': 'id_latitude',
            'placeholder': 'Select on map or enter manually',
            'readonly': 'readonly'
        }),
        required=True
    )
    longitude = forms.FloatField(
        label="Longitude",
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'id': 'id_longitude',
            'placeholder': 'Select on map or enter manually',
            'readonly': 'readonly'
        }),
        required=True
    )

    class Meta:
        model = camera
        fields = ['camera_id', 'latitude', 'longitude']
        # 'station' will be set in the view before saving the instance

    def __init__(self, *args, **kwargs):
        # Pop the station argument before calling super().__init__
        self.station = kwargs.pop('station', None)
        super().__init__(*args, **kwargs)

    def clean_camera_id(self):
        camera_id = self.cleaned_data.get('camera_id')

        if camera_id is None:
            raise forms.ValidationError("Camera Device ID is required.")

        if not self.station:
            # This should ideally be caught in the view before form processing,
            # but as a safeguard in the form:
            raise forms.ValidationError("Station information is missing. Cannot validate camera ID.")

        # Check for uniqueness within the specific station
        query = camera.objects.filter(camera_id=camera_id, station=self.station)
        
        # If we are editing an existing camera instance, exclude it from the uniqueness check
        if self.instance and self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        
        if query.exists():
            raise forms.ValidationError(f"A camera with Device ID '{camera_id}' already exists in station '{self.station.name}'.")
            
        return camera_id

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")

        if latitude is None:
            self.add_error('latitude', 'Latitude is required. Please select a point on the map.')
        elif not (-90 <= latitude <= 90):
            self.add_error('latitude', "Latitude must be between -90 and 90.")

        if longitude is None:
            self.add_error('longitude', 'Longitude is required. Please select a point on the map.')
        elif not (-180 <= longitude <= 180):
            self.add_error('longitude', "Longitude must be between -180 and 180.")
            
        return cleaned_data