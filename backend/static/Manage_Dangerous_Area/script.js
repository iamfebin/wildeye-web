// Define the key for storing data in localStorage
const STORAGE_KEY = 'dangerousAreas';

// Define the default map location and zoom level
const DEFAULT_LATITUDE =  11.55775035843068; // Default map view area - Perambra (Change to your desired location)
const DEFAULT_LONGITUDE = 75.7602342635697;
const DEFAULT_ZOOM = 14;

console.log('Script started.');

// Initialize the map
const map = L.map('map').setView([DEFAULT_LATITUDE, DEFAULT_LONGITUDE], DEFAULT_ZOOM);
console.log('Leaflet map initialized.');

// Add a tile layer (OpenStreetMap)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
console.log('Tile layer added.');

// Initialize the FeatureGroup to store drawn items
const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);
console.log('drawnItems FeatureGroup initialized and added to map.');

// Function to save drawn features to localStorage
function saveDrawnFeatures() {
    const geojson = drawnItems.toGeoJSON();
    const geojsonString = JSON.stringify(geojson);
    localStorage.setItem(STORAGE_KEY, geojsonString);
    console.log('Drawn features saved to localStorage:', geojsonString);
}

// Function to load features from localStorage
function loadDrawnFeatures() {
    console.log('Attempting to load features from localStorage...');
    const storedData = localStorage.getItem(STORAGE_KEY);
    console.log('Data retrieved from localStorage:', storedData);

    if (storedData) {
        try {
            const geojson = JSON.parse(storedData);
            console.log('Parsed GeoJSON data:', geojson);

            // Add each feature from the GeoJSON to the drawnItems group
            // This ensures they are part of the feature group linked to the edit control
            L.geoJSON(geojson, {
                style: function (feature) {
                    // Apply the dangerous area style when loading
                    return {
                        color: '#FF0000',
                        weight: 4,
                        opacity: 0.5,
                        fillColor: '#FF0000',
                        fillOpacity: 0.2
                    };
                },
                onEachFeature: function(feature, layer) {
                    drawnItems.addLayer(layer); // Add each loaded layer to the drawnItems group
                }
            });

            console.log('Drawn features loaded and added to drawnItems.');
            // Log the state of drawnItems after loading to verify
            console.log('drawnItems state after loading:', drawnItems.toGeoJSON());

        } catch (e) {
            console.error('Error parsing data from localStorage:', e);
            // Clear invalid data if parsing fails
            localStorage.removeItem(STORAGE_KEY);
            console.log('Invalid localStorage data cleared.');
        }
    } else {
        console.log('No data found in localStorage for key:', STORAGE_KEY);
    }
}

// Function to clear all dangerous areas
function clearAllDangerousAreas() {
    console.log('Clearing all dangerous areas...');
    drawnItems.clearLayers(); // Remove all layers from the FeatureGroup
    localStorage.removeItem(STORAGE_KEY); // Remove data from localStorage
    console.log('All dangerous areas cleared and localStorage entry removed.');
    // Verify localStorage is empty after removal
    console.log('localStorage after clear:', localStorage.getItem(STORAGE_KEY));
}

// Load existing features when the map is initialized
loadDrawnFeatures();


// Specify the drawing options
const drawControl = new L.Control.Draw({
    edit: {
        featureGroup: drawnItems, // Allow editing/removing of drawn shapes
        remove: true // Allow removing of drawn shapes
    },
    draw: {
        polygon: {
            shapeOptions: {
                color: '#FF0000', // Red color for dangerous areas
                weight: 4,
                opacity: 0.5,
                fillColor: '#FF0000',
                fillOpacity: 0.2
            },
            allowIntersection: false, // Prevent intersecting polygons
            drawError: {
                color: '#e1e100', // Yellow
                message: '<strong>Oh snap!<strong> you can\'t draw that!' // Error message
            },
            repeatMode: false // Tool deactivates after drawing
        },
        polyline: false, // Disable drawing polylines
        rectangle: false, // Disable drawing rectangles
        circle: false, // Disable drawing circles
        marker: false, // Disable drawing markers
        circlemarker: false // Disable drawing circle markers
    }
});
map.addControl(drawControl);
console.log('Leaflet.draw control added.');

// Add the search control (Geocoder)
L.Control.geocoder().addTo(map);
console.log('Geocoder control added.');

// --- Event Listeners ---

// Event listener for when a shape is created
map.on(L.Draw.Event.CREATED, function (event) {
    console.log('L.Draw.Event.CREATED fired.');
    const layer = event.layer;
    drawnItems.addLayer(layer); // Add the newly drawn layer to the group
    console.log('New layer added to drawnItems.');
    saveDrawnFeatures(); // Save immediately after creation
    console.log('Saved after creation.');
});

// Listen for when a layer is removed from the drawnItems FeatureGroup
// This should reliably fire after Leaflet.draw removes a layer during deletion
drawnItems.on('layerremove', function(event) {
    console.log('drawnItems "layerremove" event fired.');
    console.log('Layer removed:', event.layer.toGeoJSON());

    // Check the state of drawnItems *before* saving in layerremove handler
    const drawnItemsBeforeSave = drawnItems.toGeoJSON();
    console.log('drawnItems.toGeoJSON() BEFORE save in layerremove handler:', drawnItemsBeforeSave);

    // Save the current state of drawnItems *after* the layer has been removed
    saveDrawnFeatures();
    console.log('Saved after layer removal.');

     // Log the state of localStorage *after* saving
    console.log('localStorage content AFTER save in layerremove handler:', localStorage.getItem(STORAGE_KEY));
});


// We can keep the DELETED and EDITSTOP listeners for logging or other purposes if needed,
// but saving is now handled by the 'layerremove' event on drawnItems.
map.on(L.Draw.Event.DELETED, function (event) {
    console.log('L.Draw.Event.DELETED fired (for info).');
    const layers = event.layers; // Layers that were deleted (for logging purposes)
    layers.eachLayer(function (layer) {
         console.log('Detected deleted layer GeoJSON (from DELETED event):', layer.toGeoJSON());
    });
    // Save is handled by drawnItems.on('layerremove', ...)
});

map.on(L.Draw.Event.EDITSTOP, function (event) {
    console.log('L.Draw.Event.EDITSTOP fired (for info).');
    // Save is handled by drawnItems.on('layerremove', ...)
});


// Listen for a click on the Clear All button
document.getElementById('clear-areas').addEventListener('click', function() {
    clearAllDangerousAreas();
});
console.log('Clear All button event listener added.');

console.log('Script finished execution.');