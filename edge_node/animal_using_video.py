from ultralytics import YOLO
import cv2
import DBConnection # Your custom DBConnection module
import math
import os
import time     # Used for creating unique filenames (timestamp)
import datetime # Used for creating date-based subdirectories
import argparse # For command-line arguments
try:
    from playsound3 import playsound
except ImportError:
    try:
        from playsound import playsound
    except ImportError:
        def playsound(sound_file, block=False):
            print(f"[Sound Alert] Audio playback requested for: {sound_file}")
import mqtt_client # MQTT client for edge node telemetry & alerts

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Wild animal detection from a camera stream or image file.")
parser.add_argument('--camera-id', type=int, required=True,
                    help="The unique ID for this analysis context (e.g., from 'myapp_camera' table, or '0' for image files).")
parser.add_argument('--camera-source', type=str, default='0',
                    help="Camera source: index for local webcams (e.g., '0', '1'), "
                         "URL for IP cameras (e.g., 'rtsp://...'), "
                         "path to a video file, or path to an image file.")
args = parser.parse_args()

YOUR_CAMERA_DB_ID = args.camera_id
camera_source_input = args.camera_source # This is a string

print(f"Initializing for Analysis ID/Camera ID: {YOUR_CAMERA_DB_ID} using source: '{camera_source_input}'")

# --- Identify if the source is a single image file ---
is_image_source = False
image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
# Check if it's a string path and ends with a known image extension, and if the file exists
if isinstance(camera_source_input, str) and \
   any(camera_source_input.lower().endswith(ext) for ext in image_extensions) and \
   os.path.isfile(camera_source_input):
    is_image_source = True
    print(f"Source '{camera_source_input}' identified as a single image file.")
else:
    # If not an image file, try to convert to int for webcam index, otherwise use as string (URL/video path)
    if camera_source_input.isdigit():
        camera_source_cv = int(camera_source_input)
        print(f"Source '{camera_source_input}' identified as a webcam index.")
    else:
        camera_source_cv = camera_source_input
        print(f"Source '{camera_source_input}' identified as a video file or stream URL.")

# --- Database Connection ---
try:
    db = DBConnection.Db()
except NameError:
    print("Error: DBConnection module or Db class not found. Make sure DBConnection.py is accessible.")
    exit()
except Exception as e:
    print(f"Error initializing database connection: {e}")
    exit()

# --- Configuration for Image Saving (when detections are made) ---
BASE_SAVE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'media'))
IMAGE_SUBDIR = 'Detected_Images_Camera' # Relative to BASE_SAVE_DIR

# --- Configuration for Custom Sound ---
CUSTOM_SOUND_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'media', 'Custom_Sound_for_Detection', 'explosion-42132.mp3'))

print(f"Checking if BASE_SAVE_DIR exists at: {BASE_SAVE_DIR}")
if not os.path.exists(BASE_SAVE_DIR):
    print(f"Error: BASE_SAVE_DIR not found at {BASE_SAVE_DIR}. Creating directory...")
    os.makedirs(BASE_SAVE_DIR, exist_ok=True)

# --- Load YOLO Model ---
try:
    model_path = os.path.join(os.path.dirname(__file__), 'best.pt')
    model = YOLO(model_path) # Load your custom YOLO model
except Exception as e:
    print(f"Error loading YOLO model: {e}. Make sure 'best.pt' is in the correct location.")
    exit()

classnames = [
    'antelope', 'bear', 'cheetah', 'chimpanzee', 'coyote', 'crocodile', 'deer', 'elephant', 'flamingo',
    'fox', 'giraffe', 'gorilla', 'hedgehog', 'hippopotamus', 'hornbill', 'horse', 'hummingbird', 'hyena',
    'kangaroo', 'koala', 'leopard', 'lion', 'meerkat', 'mole', 'monkey', 'moose', 'okapi', 'orangutan',
    'ostrich', 'otter', 'panda', 'pelecaniformes', 'porcupine', 'raccoon', 'reindeer', 'rhino', 'rhinoceros',
    'snake', 'squirrel', 'swan', 'tiger', 'turkey', 'wolf', 'woodpecker', 'zebra'
]

excluded_animals = { # Define once
    "flamingo", "orangutan", "gorilla", "crocodile", "hippopotamus",
    "monkey", "rhinoceros", "hyena", "fox", "koala", "woodpecker",
    "raccoon", "otter", "ostrich", "mole", "chimpanzee", "moose",
    "okapi", "coyote", "squirrel", "snake", "meerkat", "giraffe",
    "hedgehog", "hornbill", "horse", "hummingbird", "kangaroo",
    "panda", "pelecaniformes", "porcupine", "rhino", "swan", "turkey", "zebra"
}

def process_frame_and_log_detections(frame_to_process_resized, original_frame_to_save,
                                     camera_id_for_db, yolo_model, class_names_list,
                                     db_connection, base_save_directory, image_subdirectory,
                                     alert_sound_file, animals_to_exclude, mqtt_client_instance=None):
    """
    Processes a single frame for animal detection, logs to DB, publishes MQTT event, saves image, plays sound.
    Returns the frame with drawn bounding boxes.
    """
    # Perform inference
    # For single image, stream=False is often used, but stream=True also works fine for one frame.
    # model() returns a list of Results objects for stream=False, or a generator for stream=True.
    # Looping works for both.
    results = yolo_model(frame_to_process_resized, stream=True, verbose=False)

    processed_frame_with_boxes = frame_to_process_resized.copy() # Draw on a copy

    for info in results:
        boxes = info.boxes
        for box in boxes:
            confidence = box.conf[0]
            confidence = math.ceil(confidence * 100)
            class_index = int(box.cls[0])

            if 0 <= class_index < len(class_names_list):
                detected_animal_name = class_names_list[class_index]

                if confidence > 60 and detected_animal_name not in animals_to_exclude:
                    x1, y1, x2, y2 = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                    # --- Image Saving Logic (saves a new copy upon detection) ---
                    image_saved_path_for_db = ''
                    try:
                        today = datetime.date.today()
                        # Construct path relative to MEDIA_ROOT for DB
                        date_subdir_for_db = os.path.join(image_subdirectory, str(today.year), str(today.month), str(today.day))
                        # Construct full filesystem path for saving
                        full_date_subdir_for_saving = os.path.join(base_save_directory, date_subdir_for_db)

                        os.makedirs(full_date_subdir_for_saving, exist_ok=True)

                        timestamp = int(time.time() * 1000)
                        filename = f"{detected_animal_name.lower()}_{camera_id_for_db}_{timestamp}.jpg"
                        full_image_path_to_save = os.path.join(full_date_subdir_for_saving, filename)

                        # Save the original resolution frame
                        cv2.imwrite(full_image_path_to_save, original_frame_to_save)
                        print(f"Detection image saved to: {full_image_path_to_save}")
                        
                        # Path to store in DB should be relative to MEDIA_ROOT
                        image_saved_path_for_db = os.path.join(date_subdir_for_db, filename).replace('\\', '/')
                    except Exception as e:
                        print(f"Error saving detection image: {e}")

                    # --- MQTT Publishing Logic ---
                    if mqtt_client_instance:
                        try:
                            mqtt_client_instance.publish_detection(
                                animal_name=detected_animal_name,
                                confidence=confidence,
                                image_path=image_saved_path_for_db
                            )
                        except Exception as e_mqtt:
                            print(f"Error publishing detection via MQTT: {e_mqtt}")


                    # --- Database Logic ---
                    try:
                        animal_query = "SELECT id FROM myapp_animal WHERE name = %s"
                        animal_record = db_connection.selectOne(animal_query, (detected_animal_name,))

                        if animal_record:
                            animal_db_id = animal_record['id']
                            
                            # For image file analysis (camera_id_for_db might be 0)
                            # or for actual cameras.
                            camera_is_valid_for_db = False
                            if camera_id_for_db == 0: # Special case for image file analysis
                                camera_is_valid_for_db = True
                                print(f"Using Analysis ID {camera_id_for_db} (image file source) for DB log.")
                            else: # Actual camera ID, check if it exists in DB
                                camera_check_query = "SELECT id FROM myapp_camera WHERE id = %s"
                                camera_db_record = db_connection.selectOne(camera_check_query, (camera_id_for_db,))
                                if camera_db_record:
                                    camera_is_valid_for_db = True
                                    print(f"Confirmed Camera ID {camera_db_record['id']} in database.")
                                else:
                                    print(f"Error: Configured Camera ID {camera_id_for_db} not found in 'myapp_camera' table. Skipping DB insert.")

                            if camera_is_valid_for_db:
                                qry = """
                                INSERT INTO myapp_camera_alerts (ANIMAL_id, CAMERA_id, date, time, image)
                                VALUES (%s, %s, CURDATE(), CURTIME(), %s)
                                """
                                inserted_id = db_connection.insert(qry, (animal_db_id, camera_id_for_db, image_saved_path_for_db))
                                print(f"DB: Inserted alert for Cam/Analysis ID {camera_id_for_db}, Animal {detected_animal_name}. New ID: {inserted_id}")


                                # Visuals on the displayed frame
                                cv2.rectangle(processed_frame_with_boxes, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                cv2.putText(processed_frame_with_boxes, f'{detected_animal_name} {confidence}%', (x1 + 8, y1 + 20),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                                try:
                                    if os.path.exists(alert_sound_file):
                                        playsound(alert_sound_file, block=False)
                                    else:
                                        print(f"Warning: Sound file not found at {alert_sound_file}")
                                except Exception as e_sound:
                                    print(f"Error playing sound {alert_sound_file}: {e_sound}")
                        else:
                             print(f"Warning: Detected animal '{detected_animal_name}' not found in 'myapp_animal' table. Skipping DB insert.")
                    except Exception as e_db:
                        print(f"Database error: {e_db}")
                        cv2.rectangle(processed_frame_with_boxes, (x1, y1), (x2, y2), (0, 255, 255), 2) # Yellow for DB error
                        cv2.putText(processed_frame_with_boxes, f'{detected_animal_name} (.)', (x1 + 8, y1 + 20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
            else:
                print(f"Warning: class_index {class_index} out of bounds for class_names_list (length {len(class_names_list)}).")
    
    return processed_frame_with_boxes


# --- MQTT Client Initialization ---
try:
    mqtt_cam = mqtt_client.WildEyeMQTTClient(camera_id=YOUR_CAMERA_DB_ID)
    mqtt_cam.start()
    print(f"MQTT Client initialized for Camera ID: {YOUR_CAMERA_DB_ID}")
except Exception as e_mqtt_init:
    print(f"Warning: Failed to initialize MQTT client: {e_mqtt_init}")
    mqtt_cam = None

# --- Main Processing Logic ---
try:
    if is_image_source:
        # --- Process Single Image File ---
        print(f"Loading and processing single image: {camera_source_input}")
        original_frame = cv2.imread(camera_source_input)

        if original_frame is None:
            print(f"Error: Could not read image file '{camera_source_input}'. Check path and file integrity.")
            exit()
        
        frame_resized_for_model = cv2.resize(original_frame, (640, 480)) # Resize for YOLO model

        # Process the frame
        processed_display_frame = process_frame_and_log_detections(
            frame_to_process_resized=frame_resized_for_model,
            original_frame_to_save=original_frame.copy(), # Pass the original for saving
            camera_id_for_db=YOUR_CAMERA_DB_ID,
            yolo_model=model,
            class_names_list=classnames,
            db_connection=db,
            base_save_directory=BASE_SAVE_DIR,
            image_subdirectory=IMAGE_SUBDIR,
            alert_sound_file=CUSTOM_SOUND_FILE,
            animals_to_exclude=excluded_animals,
            mqtt_client_instance=mqtt_cam
        )

        # Display the processed image
        window_title = f'Detection Result - Image: {os.path.basename(camera_source_input)} (Analysis ID: {YOUR_CAMERA_DB_ID})'
        cv2.imshow(window_title, processed_display_frame)
        print(f"Displaying processed image in window: '{window_title}'. Press any key in the window to close it.")
        key = cv2.waitKey(0) # Wait indefinitely for a key press

        if key == 27: # Esc key (optional, as any key closes for waitKey(0))
            print("Escape key pressed while viewing image.")
        
        print("Single image processing finished.")

    else:
        # --- Process Video Stream (Webcam, Video File, RTSP) ---
        print(f"Attempting to open video source: {camera_source_cv}")
        if isinstance(camera_source_cv, int) and camera_source_cv > 2:
            print(f"Webcam index '{camera_source_cv}' requested. Testing camera capture...")
            cap = cv2.VideoCapture(camera_source_cv)
            ret, test_frame = cap.read() if cap.isOpened() else (False, None)
            if not ret or test_frame is None or (test_frame.mean() < 1.0):
                print(f"Notice: Device index {camera_source_cv} is unavailable or returning blank frames. Falling back to local webcam index 0.")
                cap.release()
                camera_source_cv = 0
                cap = cv2.VideoCapture(0)
        else:
            cap = cv2.VideoCapture(camera_source_cv)

        if not cap.isOpened():
            print(f"Error: Could not open video source '{camera_source_cv}'. "
                  "Check if camera is connected, URL is correct, or video file path is valid.")
            exit()
        print("Video source opened successfully. Starting real-time detection loop...")

        while True:
            ret, frame = cap.read()
            if not ret:
                print("End of video stream or error reading frame.")
                break # Exit the loop if stream ends or error

            frame_resized_for_model = cv2.resize(frame, (640, 480))

            processed_display_frame = process_frame_and_log_detections(
                frame_to_process_resized=frame_resized_for_model,
                original_frame_to_save=frame.copy(), # Pass the original current frame for saving
                camera_id_for_db=YOUR_CAMERA_DB_ID,
                yolo_model=model,
                class_names_list=classnames,
                db_connection=db,
                base_save_directory=BASE_SAVE_DIR,
                image_subdirectory=IMAGE_SUBDIR,
                alert_sound_file=CUSTOM_SOUND_FILE,
                animals_to_exclude=excluded_animals,
                mqtt_client_instance=mqtt_cam
            )
            
            window_title = f'Animal Detection - Camera ID: {YOUR_CAMERA_DB_ID}'
            cv2.imshow(window_title, processed_display_frame)

            if cv2.waitKey(1) & 0xFF == 27:  # Press 'Esc' to exit loop
                print("Escape key pressed. Exiting video stream loop...")
                break
        
        cap.release()
        print("Video stream processing finished.")
finally:
    if mqtt_cam:
        mqtt_cam.stop()

cv2.destroyAllWindows() # Clean up any OpenCV windows
print("Script finished execution.")