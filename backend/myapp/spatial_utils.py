import math
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.validation import explain_validity

def haversine_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth's surface (in kilometers).
    """
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def extract_geometry_dict(geojson_dict):
    """
    Extract the raw geometry dictionary from a GeoJSON Feature or Geometry object.
    """
    if not isinstance(geojson_dict, dict):
        return None
    
    if geojson_dict.get('type') == 'Feature':
        return geojson_dict.get('geometry')
    elif geojson_dict.get('type') in ['Polygon', 'MultiPolygon']:
        return geojson_dict
    elif 'geometry' in geojson_dict and isinstance(geojson_dict['geometry'], dict):
        return geojson_dict['geometry']
    return geojson_dict

def validate_geojson_geometry(geojson_data):
    """
    Validates GeoJSON data to ensure it is a valid, closed, non-self-intersecting Polygon.
    Returns (is_valid: bool, result_or_error: dict/str)
    """
    geom_dict = extract_geometry_dict(geojson_data)
    if not geom_dict or not isinstance(geom_dict, dict):
        return False, "Invalid format: Expected a GeoJSON dictionary."

    geom_type = geom_dict.get('type')
    if geom_type not in ['Polygon', 'MultiPolygon']:
        return False, f"Unsupported geometry type '{geom_type}'. Must be 'Polygon' or 'MultiPolygon'."

    coordinates = geom_dict.get('coordinates')
    if not coordinates or not isinstance(coordinates, list):
        return False, "Missing or invalid 'coordinates' array."

    # Verify coordinate boundaries (-180..180, -90..90)
    def validate_coords(coords):
        for pt in coords:
            if isinstance(pt[0], list):
                if not validate_coords(pt):
                    return False
            else:
                if len(pt) < 2:
                    return False
                lon, lat = pt[0], pt[1]
                if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                    return False
        return True

    if not validate_coords(coordinates):
        return False, "Coordinates out of geographic range (Longitude [-180, 180], Latitude [-90, 90])."

    try:
        geom_shape = shape(geom_dict)
        if not geom_shape.is_valid:
            reason = explain_validity(geom_shape)
            return False, f"Invalid geometry (e.g. self-intersecting or duplicate vertices): {reason}"
        
        if geom_shape.is_empty:
            return False, "Geometry is empty."
            
        return True, geom_shape
    except Exception as e:
        return False, f"Failed to parse GeoJSON geometry: {str(e)}"

def is_polygon_within_station_buffer(geojson_data, station_lat, station_lng, buffer_km=10.0):
    """
    Checks if any part of the given polygon falls within buffer_km of the station center (lat, lng).
    Returns (intersects: bool, min_distance_km: float)
    """
    is_valid, shape_or_err = validate_geojson_geometry(geojson_data)
    if not is_valid:
        return False, float('inf')

    geom_shape = shape_or_err
    
    # Calculate distance from station to polygon centroid / boundary
    min_dist = float('inf')
    
    if isinstance(geom_shape, Polygon):
        coords = list(geom_shape.exterior.coords)
    elif isinstance(geom_shape, MultiPolygon):
        coords = []
        for poly in geom_shape.geoms:
            coords.extend(list(poly.exterior.coords))
    else:
        coords = []

    for lon, lat in coords:
        dist = haversine_distance_km(station_lat, station_lng, lat, lon)
        if dist < min_dist:
            min_dist = dist

    centroid = geom_shape.centroid
    centroid_dist = haversine_distance_km(station_lat, station_lng, centroid.y, centroid.x)
    min_dist = min(min_dist, centroid_dist)

    intersects = min_dist <= buffer_km
    return intersects, round(min_dist, 2)

from shapely.ops import nearest_points

def check_point_in_dangerous_areas(lat, lng, dangerous_area_queryset, station_queryset=None):
    """
    Checks if a point (lat, lng) lies inside any active dangerous area polygon in dangerous_area_queryset.
    Returns dict with containment status and details.
    """
    point = Point(lng, lat)  # GeoJSON uses (Longitude, Latitude)
    matching_areas = []
    nearest_area = None
    min_distance_km = float('inf')

    for area in dangerous_area_queryset:
        geojson = area.geojson_data
        is_valid, geom_shape = validate_geojson_geometry(geojson)
        if not is_valid or not geom_shape:
            continue

        is_inside = geom_shape.contains(point) or geom_shape.intersects(point)
        
        if is_inside:
            dist_km = 0.0
        else:
            # Find nearest point on the polygon boundary to calculate exact minimum distance
            nearest_geom_pt, _ = nearest_points(geom_shape, point)
            dist_km = haversine_distance_km(lat, lng, nearest_geom_pt.y, nearest_geom_pt.x)

        area_info = {
            'id': area.id,
            'station_id': area.station.id if area.station else None,
            'station_name': area.station.name if area.station else 'N/A',
            'created_at': area.created_at.isoformat() if area.created_at else None,
            'distance_to_edge_km': round(dist_km, 3)
        }

        if is_inside:
            matching_areas.append(area_info)

        if dist_km < min_distance_km:
            min_distance_km = dist_km
            nearest_area = area_info

    # Calculate nearest forest station
    nearest_station_info = None
    if station_queryset is not None:
        min_st_dist = float('inf')
        for st in station_queryset:
            if st.latitude and st.longitude:
                st_dist = haversine_distance_km(lat, lng, st.latitude, st.longitude)
                if st_dist < min_st_dist:
                    min_st_dist = st_dist
                    nearest_station_info = {
                        'id': st.id,
                        'name': st.name,
                        'distance_km': round(st_dist, 2)
                    }

    return {
        'inside_dangerous_area': len(matching_areas) > 0,
        'matched_count': len(matching_areas),
        'matching_areas': matching_areas,
        'nearest_area': nearest_area,
        'nearest_distance_km': round(min_distance_km, 3) if min_distance_km != float('inf') else None,
        'nearest_station': nearest_station_info
    }
