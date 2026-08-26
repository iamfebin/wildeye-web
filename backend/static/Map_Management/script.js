// wildeye/static/Map_Management/script.js

// Define API endpoint URLs
const API_URL = '/api/dangerous-areas/';
const STATION_API_URL = '/api/forest-stations/';
// This variable will hold the path to the public map page if available.
// It will be null if loaded from the officer map page.
// The Android app will call public_dangerous_area_map/
const PUBLIC_MAP_URL_PATH = 'public_dangerous_area_map/';


const DEFAULT_LATITUDE = 11.55775035843068; // Perambra, Kerala
const DEFAULT_LONGITUDE = 75.7602342635697;
const DEFAULT_ZOOM = 12;

console.log('Map management script started.');

// --- Global Variables for Officer's Own Station Boundary ---
let officerStationId = null;
let officerStationLat = null;
let officerStationLon = null;
let officerStationBoundary = null;
const BUFFER_RADIUS_KM = 10;
const BUFFER_STEPS = 64;

// NEW: Variable to check if this is the public map view
let isPublicMapView = false;

const map = L.map('map').setView([DEFAULT_LATITUDE, DEFAULT_LONGITUDE], DEFAULT_ZOOM);
console.log('Leaflet map initialized.');

function getOfficerOwnStationInfo() {
    const stationIdMeta = document.querySelector('meta[name="officer-station-id"]');
    const latMeta = document.querySelector('meta[name="officer-station-latitude"]');
    const lonMeta = document.querySelector('meta[name="officer-station-longitude"]');

    if (stationIdMeta && latMeta && lonMeta && !isNaN(parseFloat(latMeta.content)) && !isNaN(parseFloat(lonMeta.content))) {
        officerStationId = parseInt(stationIdMeta.content);
        officerStationLat = parseFloat(latMeta.content);
        officerStationLon = parseFloat(lonMeta.content);
        console.log(`Current Officer Station Coords: Lat ${officerStationLat}, Lon ${officerStationLon}`);

        const centerPoint = turf.point([officerStationLon, officerStationLat]);
        officerStationBoundary = turf.buffer(centerPoint, BUFFER_RADIUS_KM, { units: 'kilometers', steps: BUFFER_STEPS });

        map.setView([officerStationLat, officerStationLon], DEFAULT_ZOOM);
    } else {
        // If officer station meta tags are not present, it's likely the public view
        console.log('Officer station meta tags not found. Assuming public map view.');
        isPublicMapView = true;
    }
}

// Determine if public view immediately
getOfficerOwnStationInfo();

// --- Multi-Layer Base Map Switcher ---
const osmStandard = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
});

const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and GIS User Community'
});

const openTopoMap = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    maxZoom: 17,
    attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Style: OpenTopoMap'
});

const cartoDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
});

// Set default tile layer to Standard OpenStreetMap
osmStandard.addTo(map);

const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

const cameraLayerGroup = L.layerGroup();
const animalAlertLayerGroup = L.layerGroup();

// Only add camera and alerts to map if NOT public view
if (!isPublicMapView) {
    cameraLayerGroup.addTo(map);
    animalAlertLayerGroup.addTo(map);
}

// Register Base Maps & Overlay Layers for Control Switcher
const baseMaps = {
    "🗺️ Standard": osmStandard,
    "🛰️ Satellite": esriSatellite,
    "🏔️ Topography": openTopoMap,
    "🌙 Dark": cartoDark
};

// Only expose non-sensitive overlays to public view
const overlayMaps = {
    "⚠️ Dangerous Areas": drawnItems
};

if (!isPublicMapView) {
    overlayMaps["📷 Forest Cameras"] = cameraLayerGroup;
    overlayMaps["🚨 Live Animal Alerts"] = animalAlertLayerGroup;
}

// Add Control Switcher to Map
L.control.layers(baseMaps, overlayMaps, { position: 'topright', collapsed: false }).addTo(map);
console.log('Multi-layer tile switcher and overlay controls added to map.');

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
const csrftoken = getCookie('csrftoken');




async function loadStationBoundaries() {
    console.log('Attempting to load all forest station boundaries...');
    try {
        const response = await fetch(STATION_API_URL);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Forest station data retrieved:', data);

        // --- CORRECTED CONDITION HERE ---
        // If the API returns a direct array of stations, check data.length
        if (data && Array.isArray(data) && data.length > 0) {
            data.forEach(station => { // Iterate directly over 'data'
                if (station.latitude && station.longitude) {
                    const centerPoint = turf.point([station.longitude, station.latitude]);
                    const boundaryPolygon = turf.buffer(centerPoint, BUFFER_RADIUS_KM, { units: 'kilometers', steps: BUFFER_STEPS });

                    const isOfficerStation = !isPublicMapView && (officerStationId && station.id === officerStationId);

                    L.geoJSON(boundaryPolygon, {
                        className: isOfficerStation ? 'officer-station-boundary' : 'other-station-boundary',
                        style: function (feature) {
                            return {
                                color: isOfficerStation ? '#007bff' : '#88BBDD',
                                weight: isOfficerStation ? 2 : 1.5,
                                opacity: 0.7,
                                fillColor: isOfficerStation ? '#007bff' : '#ADD8E6',
                                fillOpacity: isOfficerStation ? 0.1 : 0.05
                            };
                        }
                    }).addTo(map)
                        .bindPopup(`<b>${station.name}</b><br>Station ID: ${station.id}`)
                        .on('mouseover', function (e) {
                            this.openPopup();
                        })
                        .on('mouseout', function (e) {
                            this.closePopup();
                        });
                }
            });
            console.log('All forest station boundaries drawn on map.');
        } else {
            console.log('No forest station data found.');
        }
    } catch (e) {
        console.error('Error loading forest station boundaries:', e);
    }
}

//         if (data && data.results && data.results.length > 0) {
//             data.results.forEach(station => {
//                 if (station.latitude && station.longitude) {
//                     const centerPoint = turf.point([station.longitude, station.latitude]);
//                     const boundaryPolygon = turf.buffer(centerPoint, BUFFER_RADIUS_KM, { units: 'kilometers', steps: BUFFER_STEPS });

//                     // Only differentiate if it's the officer's own map
//                     const isOfficerStation = !isPublicMapView && (officerStationId && station.id === officerStationId);

//                     L.geoJSON(boundaryPolygon, {
//                         className: isOfficerStation ? 'officer-station-boundary' : 'other-station-boundary',
//                         style: function (feature) {
//                             return {
//                                 color: isOfficerStation ? '#007bff' : '#88BBDD',
//                                 weight: isOfficerStation ? 2 : 1.5,
//                                 opacity: 0.7,
//                                 fillColor: isOfficerStation ? '#007bff' : '#ADD8E6',
//                                 fillOpacity: isOfficerStation ? 0.1 : 0.05
//                             };
//                         }
//                     }).addTo(map)
//                     .bindPopup(`<b>${station.name}</b><br>Station ID: ${station.id}`)
//                     .on('mouseover', function (e) {
//                         this.openPopup();
//                     })
//                     .on('mouseout', function (e) {
//                         this.closePopup();
//                     });
//                 }
//             });
//             console.log('All forest station boundaries drawn on map.');
//         } else {
//             console.log('No forest station data found.');
//         }
//     } catch (e) {
//         console.error('Error loading forest station boundaries:', e);
//         // alert('Failed to load forest station boundaries. Please check your network.'); // Remove alert for public view
//     }
// }


async function loadDrawnFeatures() {
    console.log('Attempting to load dangerous areas from backend...');
    try {
        const response = await fetch(API_URL);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Dangerous area data retrieved:', data);

        drawnItems.clearLayers();

        if (data && data.results && data.results.length > 0) {
            data.results.forEach(featureData => {
                const geojson = featureData.geojson_data;
                const areaId = featureData.id;
                const stationName = featureData.station_name;
                const featureStationId = featureData.station;

                if (geojson && geojson.geometry && geojson.geometry.type === 'Polygon') {
                    const layer = L.geoJSON(geojson, {
                        style: function (feature) {
                            return {
                                color: '#FF0000',
                                weight: 4,
                                opacity: 0.5,
                                fillColor: '#FF0000',
                                fillOpacity: 0.2
                            };
                        }
                    });

                    layer.eachLayer(function (l) {
                        l.backendId = areaId;
                        l.stationName = stationName;
                        l.stationId = featureStationId;
                        l.bindPopup(`<b>Dangerous Area</b><br>Station: ${stationName || 'N/A'} (ID: ${featureStationId})`);
                        drawnItems.addLayer(l);
                    });
                }
            });
            console.log('Drawn dangerous areas loaded and added to drawnItems.');
        } else {
            console.log('No dangerous areas found in backend.');
        }
    } catch (e) {
        console.error('Error loading dangerous areas from backend:', e);
        // alert('Failed to load dangerous areas from the server. Please check your network.'); // Remove alert for public view
    }
}


// These functions are only relevant for the officer's map, so conditionally define/call them.
let drawControl = null; // Initialize drawControl as null

if (!isPublicMapView) { // Only enable drawing/editing controls for officers
    console.log('Officer mode detected. Initializing drawing controls.');

    const BUFFER_RADIUS_KM = 10;
    const BUFFER_STEPS = 64;

    function isValidAreaForOfficer(polygonLayer) {
        if (!officerStationBoundary) {
            console.warn('Officer station boundary not defined. Skipping client-side boundary validation.');
            return true;
        }

        const drawnPolygonTurf = polygonLayer.toGeoJSON();
        const intersects = turf.booleanIntersects(drawnPolygonTurf, officerStationBoundary);

        if (!intersects) {
            alert(`Warning: This area is outside your assigned station's allowed drawing zone (${BUFFER_RADIUS_KM} km radius). Please draw within the blue boundary.`);
            return false;
        }
        return true;
    }

    async function saveNewFeature(layer) {
        console.log('Saving new feature to backend...');
        if (!officerStationId) {
            alert("Cannot save: Your officer session is not properly linked to a station ID. Please re-login.");
            drawnItems.removeLayer(layer);
            return;
        }
        if (!isValidAreaForOfficer(layer)) {
            drawnItems.removeLayer(layer);
            return;
        }
        const geojson = layer.toGeoJSON();
        const data = {
            geojson_data: geojson,
            station_id: parseInt(officerStationId)
        };
        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify(data)
            });
            if (!response.ok) {
                const errorData = await response.json();
                console.error('Error saving feature:', response.status, errorData);
                alert(`Failed to save area: ${JSON.stringify(errorData.detail || errorData.non_field_errors || 'Unknown error')}`);
                drawnItems.removeLayer(layer);
                return;
            }
            const savedData = await response.json();
            layer.backendId = savedData.id;
            layer.stationName = savedData.station_name;
            layer.stationId = savedData.station;
            layer.bindPopup(`<b>Dangerous Area</b><br>Station: ${savedData.station_name || 'N/A'} (ID: ${savedData.station})`);
            console.log('New feature saved to backend with ID:', savedData.id);
        } catch (e) {
            console.error('Network error during save:', e);
            alert('Network error while saving area. Please try again.');
            drawnItems.removeLayer(layer);
        }
    }

    async function updateFeature(layer) {
        console.log('Updating feature in backend with ID:', layer.backendId);
        if (layer.stationId !== parseInt(officerStationId)) {
            alert("You can only edit dangerous areas assigned to your own station.");
            return;
        }
        if (!isValidAreaForOfficer(layer)) {
            return;
        }
        if (!layer.backendId) {
            console.error('Cannot update: Layer has no backend ID.');
            alert('Cannot update: This area was not loaded from the server or has no ID.');
            return;
        }
        const geojson = layer.toGeoJSON();
        const data = {
            geojson_data: geojson,
            station_id: parseInt(officerStationId)
        };
        try {
            const response = await fetch(`${API_URL}${layer.backendId}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify(data)
            });
            if (!response.ok) {
                const errorData = await response.json();
                console.error('Error updating feature:', response.status, errorData);
                alert(`Failed to update area: ${JSON.stringify(errorData.detail || errorData.non_field_errors || 'Unknown error')}`);
                return;
            }
            console.log('Feature updated successfully in backend.');
        } catch (e) {
            console.error('Network error during update:', e);
            alert('Network error while updating area. Please try again.');
        }
    }

    async function deleteFeature(layer) {
        console.log('Deleting feature from backend with ID:', layer.backendId);
        if (layer.stationId !== parseInt(officerStationId)) {
            alert("You can only delete dangerous areas assigned to your own station.");
            return;
        }
        if (!layer.backendId) {
            console.error('Cannot delete: Layer has no backend ID.');
            alert('Cannot delete: This area was not loaded from the server or has no ID.');
            return;
        }
        try {
            const response = await fetch(`${API_URL}${layer.backendId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': csrftoken,
                },
            });
            if (!response.ok) {
                const errorData = await response.json();
                console.error('Error deleting feature:', response.status, errorData);
                alert(`Failed to delete area: ${JSON.stringify(errorData.detail || errorData.non_field_errors || 'Unknown error')}`);
                return;
            }
            console.log('Feature deleted successfully from backend.');
        } catch (e) {
            console.error('Network error during delete:', e);
            alert('Network error while deleting area. Please try again.');
        }
    }

    async function clearAllDangerousAreas() {
        console.log('Attempting to clear all dangerous areas from backend...');
        const layersToDelete = [];
        drawnItems.eachLayer(function (layer) {
            if (layer.backendId && layer.stationId === parseInt(officerStationId)) {
                layersToDelete.push(layer);
            }
        });
        if (layersToDelete.length === 0) {
            alert('No dangerous areas assigned to your station to clear.');
            return;
        }
        if (!confirm(`Are you sure you want to clear ALL ${layersToDelete.length} dangerous areas assigned to your station? This cannot be undone.`)) {
            return;
        }
        let successCount = 0;
        let failCount = 0;
        const removedLayers = [];
        for (const layer of layersToDelete) {
            try {
                const response = await fetch(`${API_URL}${layer.backendId}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': csrftoken,
                    },
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    console.error(`Failed to delete area ID ${layer.backendId}:`, response.status, errorData);
                    failCount++;
                } else {
                    successCount++;
                    removedLayers.push(layer);
                }
            } catch (e) {
                console.error(`Network error deleting area ID ${layer.backendId}:`, e);
                failCount++;
            }
        }
        removedLayers.forEach(layer => {
            drawnItems.removeLayer(layer);
        });
        if (successCount > 0 || failCount > 0) {
            alert(`Clear operation complete: ${successCount} areas cleared, ${failCount} failed to delete.`);
        } else {
            alert('No areas were cleared. Check console for errors.');
        }
        console.log('Clear All operation completed.');
    }


    // Initialize Leaflet.draw control ONLY if NOT in public view
    drawControl = new L.Control.Draw({
        edit: {
            featureGroup: drawnItems,
            remove: true
        },
        draw: {
            polygon: {
                shapeOptions: {
                    color: '#FF0000',
                    weight: 4,
                    opacity: 0.5,
                    fillColor: '#FF0000',
                    fillOpacity: 0.2
                },
                allowIntersection: false,
                drawError: {
                    color: '#e1e100',
                    message: '<strong>Oh snap!</strong> you can\'t draw that!'
                },
                repeatMode: false
            },
            polyline: false, rectangle: false, circle: false, marker: false, circlemarker: false
        }
    });
    map.addControl(drawControl);
    console.log('Leaflet.draw control added.');

    // Add the search control (Geocoder)
    L.Control.geocoder().addTo(map);
    console.log('Geocoder control added.');

    // --- Event Listeners (only for officer-managed map) ---
    map.on(L.Draw.Event.CREATED, async function (event) {
        console.log('L.Draw.Event.CREATED fired.');
        const layer = event.layer;
        drawnItems.addLayer(layer);
        await saveNewFeature(layer);
    });

    map.on(L.Draw.Event.EDITED, async function (event) {
        console.log('L.Draw.Event.EDITED fired.');
        const layers = event.layers;
        layers.eachLayer(async function (layer) {
            await updateFeature(layer);
        });
    });

    map.on(L.Draw.Event.DELETED, async function (event) {
        console.log('L.Draw.Event.DELETED fired.');
        const layers = event.layers;
        layers.eachLayer(async function (layer) {
            await deleteFeature(layer);
        });
    });

    const clearAreasButton = document.getElementById('clear-areas');
    if (clearAreasButton) {
        clearAreasButton.addEventListener('click', async function () {
            await clearAllDangerousAreas();
        });
    }


} else {
    // PUBLIC VIEW: Disable drawing controls explicitly if they were somehow initialized
    if (map.hasControl(L.Control.Draw)) {
        map.removeControl(L.Control.Draw);
    }
    // L.Control.Draw adds its own toolbar. If not removed, hide it via CSS.
    // CSS in Public_Dangerous_Area_Map.html already handles hiding.
    console.log('Public view detected. Drawing controls disabled.');

    // Add the search control (Geocoder) for public view too
    L.Control.geocoder().addTo(map);
    console.log('Geocoder control added for public view.');
}


// --- New Map Layers: Forest Cameras & Live Animal Alerts ---
function getAnimalEmoji(animalName) {
    if (!animalName) return '🐾';
    const name = animalName.toLowerCase();
    if (name.includes('tiger')) return '🐅';
    if (name.includes('elephant')) return '🐘';
    if (name.includes('leopard') || name.includes('panther')) return '🐆';
    if (name.includes('bear')) return '🐻';
    if (name.includes('boar') || name.includes('pig')) return '🐗';
    if (name.includes('deer') || name.includes('sambar')) return '🦌';
    if (name.includes('monkey') || name.includes('macaque') || name.includes('langur')) return '🐒';
    if (name.includes('snake') || name.includes('python') || name.includes('cobra')) return '🐍';
    if (name.includes('bison') || name.includes('gaur')) return '🦬';
    return '🐾';
}

async function loadMapCameras() {
    try {
        const url = officerStationId ? `/api/map-cameras/?station_id=${officerStationId}` : '/api/map-cameras/';
        const response = await fetch(url);
        if (!response.ok) return;
        const cameras = await response.json();
        cameraLayerGroup.clearLayers();

        cameras.forEach(cam => {
            if (cam.latitude && cam.longitude) {
                const cameraIcon = L.divIcon({
                    className: 'custom-camera-marker-icon',
                    html: `<div style="background: #1e40af; color: white; padding: 4px 8px; border-radius: 16px; font-weight: bold; font-size: 11px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); border: 2px solid #ffffff; display: inline-flex; align-items: center; gap: 4px;">📷 Cam #${cam.camera_id}</div>`,
                    iconSize: [85, 26],
                    iconAnchor: [42, 13]
                });

                const marker = L.marker([cam.latitude, cam.longitude], { icon: cameraIcon });
                marker.bindPopup(`
                    <div style="font-family: Arial, sans-serif; padding: 4px; min-width: 160px;">
                        <h4 style="margin: 0 0 6px 0; color: #1e40af;">📷 Camera #${cam.camera_id}</h4>
                        <p style="margin: 3px 0; font-size: 0.9em;"><b>Station:</b> ${cam.station_name || 'Unassigned'}</p>
                        <p style="margin: 3px 0; font-size: 0.85em; color: #64748b;">Lat: ${cam.latitude.toFixed(4)}, Lng: ${cam.longitude.toFixed(4)}</p>
                    </div>
                `);
                cameraLayerGroup.addLayer(marker);
            }
        });
        console.log(`Loaded ${cameras.length} cameras onto map.`);
    } catch (e) {
        console.error('Error loading map cameras:', e);
    }
}

async function loadMapAnimalAlerts() {
    try {
        const url = officerStationId ? `/api/map-animal-alerts/?station_id=${officerStationId}` : '/api/map-animal-alerts/';
        const response = await fetch(url);
        if (!response.ok) return;
        const alerts = await response.json();
        animalAlertLayerGroup.clearLayers();

        alerts.forEach(alert => {
            if (alert.latitude && alert.longitude) {
                const emoji = getAnimalEmoji(alert.animal_name);
                const alertIcon = L.divIcon({
                    className: 'custom-alert-marker-icon',
                    html: `
                        <div style="position: relative; display: inline-block;">
                            <div style="background: #dc2626; color: white; padding: 5px 10px; border-radius: 20px; font-weight: bold; font-size: 12px; box-shadow: 0 3px 8px rgba(0,0,0,0.4); border: 2px solid #ffffff; display: inline-flex; align-items: center; gap: 4px;">
                                ${emoji} ${alert.animal_name}
                            </div>
                        </div>
                    `,
                    iconSize: [110, 30],
                    iconAnchor: [55, 15]
                });

                const marker = L.marker([alert.latitude, alert.longitude], { icon: alertIcon });
                const imgHtml = alert.image_url
                    ? `<img src="${alert.image_url}" style="width: 100%; max-height: 130px; object-fit: cover; border-radius: 6px; margin-top: 6px; border: 1px solid #cbd5e1;" alt="${alert.animal_name}"/>`
                    : '';

                marker.bindPopup(`
                    <div style="font-family: Arial, sans-serif; min-width: 190px; padding: 2px;">
                        <h4 style="margin: 0 0 4px 0; color: #dc2626; display: flex; align-items: center; gap: 6px;">
                            ${emoji} ${alert.animal_name} Detected
                        </h4>
                        <p style="margin: 2px 0; font-size: 0.88em;"><b>Camera:</b> #${alert.camera_number} (${alert.station_name})</p>
                        <p style="margin: 2px 0; font-size: 0.82em; color: #64748b;"><b>Time:</b> ${alert.date || ''} ${alert.time || ''}</p>
                        ${imgHtml}
                    </div>
                `);
                animalAlertLayerGroup.addLayer(marker);
            }
        });
        console.log(`Loaded ${alerts.length} animal alerts onto map.`);
    } catch (e) {
        console.error('Error loading map animal alerts:', e);
    }
}

// --- Initial Setup Sequence ---
// 1. (Already initialized and retrieved at top of script: getOfficerOwnStationInfo)

// 2. Load and draw ALL station boundaries (from API)
loadStationBoundaries();

// 3. Load and draw all existing dangerous areas (from API)
loadDrawnFeatures();

// 4. Load cameras and live animal alerts ONLY for Forest Officers (not public map)
if (!isPublicMapView) {
    loadMapCameras();
    loadMapAnimalAlerts();
} else {
    console.log('Public map view active. Camera and animal alert markers hidden.');
}

console.log('Map script finished execution and initial setup initiated.');
