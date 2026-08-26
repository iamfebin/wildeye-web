# myapp/context_processors.py
from .models import forest_officer # Adjust import as per your project structure

def officer_profile_context(request):
    # Initialize with default values
    context = {
        'officer_first_name': "Officer",
        'officer_last_name': "",
        'officer_station_name': "N/A Station", # Default station name
        'officer_image_url': None
    }

    if request.session.get('is_authenticated') and request.session.get('user_type') == 'officer':
        login_id = request.session.get('user_id')
        if login_id:
            try:
                # Use select_related to efficiently fetch related Station object
                officer = forest_officer.objects.select_related('STATION').get(LOGIN_id=login_id)
                
                context['officer_first_name'] = officer.first_name
                context['officer_last_name'] = officer.last_name # Add last name
                
                if officer.STATION: # Check if station is assigned
                    context['officer_station_name'] = officer.STATION.name
                else:
                    context['officer_station_name'] = "Unassigned Station" # Fallback if station is somehow null

                if officer.image and hasattr(officer.image, 'url'):
                    context['officer_image_url'] = officer.image.url
                else:
                    context['officer_image_url'] = None # Explicitly set to None if no image

            except forest_officer.DoesNotExist:
                # Officer not found, defaults will be used
                print(f"Officer with LOGIN_id {login_id} not found. Using default context.")
            except Exception as e:
                # Log other potential errors
                print(f"Error in officer_profile_context for LOGIN_id {login_id}: {e}. Using default context.")
    
    return context