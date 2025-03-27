import os
import uuid
import time
from datetime import datetime, timedelta
from threading import Thread
from queue import Queue
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration from environment variables
PORT = int(os.getenv('PORT', '3000'))
VALID_API_KEYS = os.getenv('VALID_API_KEYS', '123456789').split(',')
DEFAULT_RECAPTCHA_URL = os.getenv('DEFAULT_RECAPTCHA_URL', 'https://www.google.com/recaptcha/api2/demo')
DEFAULT_RECAPTCHA_SITEKEY = os.getenv('DEFAULT_RECAPTCHA_SITEKEY', '6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-')
DEFAULT_HEADLESS = os.getenv('DEFAULT_HEADLESS', 'false').lower() == 'true'
DEFAULT_INCOGNITO = os.getenv('DEFAULT_INCOGNITO', 'true').lower() == 'true'
MAX_PARALLEL_TASKS = int(os.getenv('MAX_PARALLEL_TASKS', '5'))
RETRY_COUNT = int(os.getenv('RETRY_COUNT', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5000'))
PAGE_LOAD_TIMEOUT = int(os.getenv('PAGE_LOAD_TIMEOUT', '30000'))

# Store for tasks
task_store: Dict[str, Dict[str, Any]] = {}

# Request Queue implementation
class RequestQueue:
    def __init__(self, max_parallel=5):
        self.queue = Queue()
        self.processing = 0
        self.max_parallel = max_parallel
        self.worker_thread = Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def add(self, task_id: str, func, *args, **kwargs):
        self.queue.put((task_id, func, args, kwargs))
    
    def _process_queue(self):
        while True:
            if self.processing < self.max_parallel and not self.queue.empty():
                self.processing += 1
                task_id, func, args, kwargs = self.queue.get()
                
                # Execute the task in a separate thread
                thread = Thread(target=self._execute_task, args=(task_id, func, args, kwargs))
                thread.daemon = True
                thread.start()
            
            time.sleep(0.1)
    
    def _execute_task(self, task_id, func, args, kwargs):
        try:
            result = func(*args, **kwargs)
            if result.get('success') == 1:
                update_task_status(task_id, "ready", {"gRecaptchaResponse": result.get('gRecaptchaResponse')})
            else:
                update_task_status(task_id, "failed", {"error": result.get('error', 'Unknown error')})
        except Exception as e:
            update_task_status(task_id, "failed", {"error": str(e)})
        finally:
            self.processing -= 1

# Initialize queue
request_queue = RequestQueue(MAX_PARALLEL_TASKS)

# Helper functions
def update_task_status(task_id: str, status: str, data: Optional[Dict[str, Any]] = None):
    if task_id not in task_store:
        raise ValueError('Task not found')
    
    task_store[task_id].update({
        'status': status,
        **(data or {})
    })

def validate_api_key(func):
    def wrapper(*args, **kwargs):
        data = request.get_json()
        client_key = data.get('clientKey') if data else None
        
        if not client_key or client_key not in VALID_API_KEYS:
            return jsonify({
                'success': 0,
                'message': 'Invalid API key'
            }), 401
        
        return func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    return wrapper

# reCAPTCHA Solver class
class RecaptchaSolver:
    def __init__(self):
        self.retry_count = RETRY_COUNT
        self.retry_delay = RETRY_DELAY
    
    def solve(self, url: str, sitekey: str) -> Dict[str, Any]:
        with sync_playwright() as playwright:
            try:
                browser = self._init_browser(playwright)
                page = browser.new_page()
                page._sitekey = sitekey  # Store sitekey for later use
                
                print(f"Navigating to {url}")
                page.goto(url, timeout=PAGE_LOAD_TIMEOUT)
                print("Page loaded")
                
                # Wait a bit after page load
                page.wait_for_timeout(2000)
                
                print("Injecting custom script...")
                self._inject_custom_script(page, sitekey)
                
                print("Handling reCAPTCHA...")
                recaptcha_token = self._handle_recaptcha(page)
                
                return {
                    'success': 1,
                    'message': "ready",
                    'gRecaptchaResponse': recaptcha_token
                }
            except Exception as e:
                print(f"Error in solve: {str(e)}")
                return {
                    'success': 0,
                    'message': "failed",
                    'error': str(e)
                }
            finally:
                if 'browser' in locals():
                    browser.close()
    
    def _init_browser(self, playwright):
        # Path to extension directory - adjust as needed for your setup
        extension_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs", "rektCaptcha")
        
        # Create the extensions directory if it doesn't exist
        os.makedirs(extension_path, exist_ok=True)
        
        # Check if extension files exist, and if not, create them
        self._prepare_extension_files(extension_path)
        
        # Using chromium from playwright with extension
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir="",  # Empty string creates a temporary profile
            headless=DEFAULT_HEADLESS,
            args=[
                f'--disable-extensions-except={extension_path}',
                f'--load-extension={extension_path}',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ],
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        
        return browser
        
    def _prepare_extension_files(self, extension_path):
        """Create the necessary files for the rektCaptcha extension"""
        manifest_path = os.path.join(extension_path, "manifest.json")
        background_path = os.path.join(extension_path, "background.js")
        content_path = os.path.join(extension_path, "content.js")
        
        # Create manifest.json if it doesn't exist
        if not os.path.exists(manifest_path):
            manifest_content = {
                "name": "rektCaptcha",
                "version": "1.0",
                "manifest_version": 3,
                "description": "Helps solve reCAPTCHA challenges",
                "permissions": ["activeTab", "scripting"],
                "background": {
                    "service_worker": "background.js"
                },
                "content_scripts": [
                    {
                        "matches": ["*://*/*"],
                        "js": ["content.js"],
                        "all_frames": True
                    }
                ]
            }
            
            with open(manifest_path, 'w') as f:
                json.dump(manifest_content, f, indent=2)
                
        # Create background.js if it doesn't exist
        if not os.path.exists(background_path):
            background_content = """
// Helper functions for solving reCAPTCHA
console.log('rektCaptcha extension background script loaded');

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'captchaDetected') {
    console.log('CAPTCHA detected on page');
  }
});
"""
            with open(background_path, 'w') as f:
                f.write(background_content)
                
        # Create content.js if it doesn't exist
        if not os.path.exists(content_path):
            content_script = """
// rektCaptcha content script
console.log('rektCaptcha content script loaded');

// Monitor for reCAPTCHA elements
function detectRecaptcha() {
  const recaptchaFrames = document.querySelectorAll('iframe[src*="recaptcha"]');
  if (recaptchaFrames.length > 0) {
    chrome.runtime.sendMessage({action: 'captchaDetected'});
  }
  
  // Helper for image recognition tasks
  window.solveImageChallenge = function(detectedObjects) {
    // In a real implementation, this would analyze the images
    // For now, just report back what was detected
    console.log('Objects detected in challenge:', detectedObjects);
  };
}

// Run detection
detectRecaptcha();
document.addEventListener('DOMContentLoaded', detectRecaptcha);
"""
            with open(content_path, 'w') as f:
                f.write(content_script)
    
    def _inject_custom_script(self, page, sitekey):
        page.evaluate("""(key) => {
            document.body.innerHTML = '';
            document.head.innerHTML = '';

            const style = document.createElement('style');
            style.textContent = `
                body {
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    padding: 0;
                    background-color: #000080;
                }
                .scale {
                    transform: scale(1.2);
                    transform-origin: center;
                    margin: 20px;
                    position: relative;
                    z-index: 9999;
                }
                .g-recaptcha {
                    position: relative !important;
                    z-index: 9999 !important;
                }
                .g-recaptcha iframe {
                    position: relative !important;
                    z-index: 9999 !important;
                }
                textarea {
                    width: 800px;
                    height: 300px;
                    margin-top: 20px;
                    padding: 10px;
                    border-radius: 5px;
                    border: 1px solid #ccc;
                    resize: vertical;
                }
            `;
            document.head.appendChild(style);

            const form = document.createElement('form');
            form.method = 'POST';

            const recaptchaDiv = document.createElement('div');
            recaptchaDiv.className = 'g-recaptcha scale';
            recaptchaDiv.dataset.sitekey = key;
            recaptchaDiv.dataset.callback = 'submit';

            const displayTextarea = document.createElement('textarea');
            displayTextarea.id = 'g-recaptcha-response';
            displayTextarea.name = 'g-recaptcha-response';
            displayTextarea.placeholder = 'Token will appear here...';
            displayTextarea.readOnly = true;

            form.appendChild(recaptchaDiv);
            form.appendChild(displayTextarea);
            document.body.appendChild(form);

            window.submit = function (token) {
                displayTextarea.value = token;
                return false;
            };

            const script = document.createElement('script');
            script.src = 'https://www.google.com/recaptcha/api.js';
            script.async = true;
            script.defer = true;
            document.head.appendChild(script);
        }""", sitekey)
        
        # Wait for reCAPTCHA script to load
        page.wait_for_function("""() => {
            return typeof window.grecaptcha !== 'undefined' && window.grecaptcha.ready;
        }""", timeout=30000)
        
        print('reCAPTCHA iframe is visible')
    
    def _handle_recaptcha(self, page):
        print('Waiting for reCAPTCHA to be checked...')
        attempt = 0
        
        while attempt < self.retry_count:
            try:
                # Wait for iframe to appear
                page.wait_for_selector('iframe[title="reCAPTCHA"]', 
                                      timeout=20000, 
                                      state='attached')
                
                frame = page.frame_locator('iframe[title="reCAPTCHA"]')
                print('iframe reCAPTCHA Found')
                
                # Wait and ensure checkbox is visible
                checkbox = frame.locator('#recaptcha-anchor')
                checkbox.wait_for(state='visible', timeout=20000)
                print('Checkbox is visible')
                
                # Wait a bit to ensure checkbox is ready for interaction
                page.wait_for_timeout(2000)
                
                # Try clicking a few times if necessary
                clicked = False
                for i in range(3):
                    try:
                        checkbox.evaluate("""node => {
                            // Scroll to element
                            node.scrollIntoView({
                                behavior: 'smooth',
                                block: 'center',
                                inline: 'center'
                            });
                        }""")
                        
                        page.wait_for_timeout(500)
                        
                        # Try clicking with JavaScript
                        checkbox.evaluate("node => node.click()")
                        clicked = True
                        print('Clicked checkbox using JavaScript')
                        break
                    except Exception as e:
                        print(f"Click attempt {i + 1} failed: {str(e)}")
                        page.wait_for_timeout(1000)
                
                if not clicked:
                    raise Exception('Failed to click checkbox after multiple attempts')
                
                # Now check if we got an image challenge
                try:
                    # Wait a bit for image challenge to appear (if it does)
                    page.wait_for_timeout(3000)
                    
                    # Check for image challenge frame
                    challenge_frame = page.frame_locator('iframe[title="recaptcha challenge expires in two minutes"]')
                    challenge_exists = challenge_frame.locator('div.rc-imageselect-desc').count() > 0
                    
                    if challenge_exists:
                        print("Image challenge detected, attempting to solve...")
                        self._solve_image_challenge(page, challenge_frame)
                except Exception as challenge_error:
                    print(f"No image challenge found or error: {str(challenge_error)}")
                
                # Wait for verification (either direct or after image challenge)
                try:
                    frame.locator('#recaptcha-anchor[aria-checked="true"]').wait_for(timeout=120000)
                    print('reCAPTCHA successfully checked!')
                except Exception as verify_error:
                    print(f"Failed to verify checkbox is checked: {str(verify_error)}")
                    # Continue anyway as we might still get a token
                
                # Wait for token with polling
                token = page.evaluate("""() => {
                    return new Promise((resolve) => {
                        let attempts = 0;
                        const maxAttempts = 30;
                        const checkInterval = setInterval(() => {
                            attempts++;
                            const responseInput = document.querySelector('#g-recaptcha-response');
                            const response = responseInput && responseInput.value;
                            console.log(`Token check attempt ${attempts}: ${response ? 'found' : 'not found'}`);

                            if (response) {
                                clearInterval(checkInterval);
                                resolve(response);
                            }

                            if (attempts >= maxAttempts) {
                                clearInterval(checkInterval);
                                resolve(null);
                            }
                        }, 1000);
                    });
                }""")
                
                if token:
                    print('Got reCAPTCHA response')
                    return token
                
                raise Exception('No reCAPTCHA response found')
                
            except Exception as e:
                attempt += 1
                print(f"reCAPTCHA attempt {attempt} failed: {str(e)}")
                
                if attempt < self.retry_count:
                    print(f"Waiting {self.retry_delay / 1000} seconds before retrying...")
                    time.sleep(self.retry_delay / 1000)
                    
                    # Refresh the page and reinject
                    page.reload(timeout=30000, wait_until="networkidle")
                    page.wait_for_timeout(2000)
                    self._inject_custom_script(page, page._sitekey)
        
        raise Exception('Failed to handle reCAPTCHA after maximum attempts')
        
    def _solve_image_challenge(self, page, challenge_frame):
        """Attempt to solve the image challenge"""
        try:
            # First, identify what we're looking for
            challenge_text = challenge_frame.locator('.rc-imageselect-desc-no-canonical').text_content()
            if not challenge_text:
                challenge_text = challenge_frame.locator('.rc-imageselect-desc').text_content()
                
            print(f"Challenge text: {challenge_text}")
            
            # Determine what we're looking for
            target_objects = []
            if "bus" in challenge_text.lower():
                target_objects.append("bus")
            elif "car" in challenge_text.lower():
                target_objects.append("car")
            elif "fire hydrant" in challenge_text.lower():
                target_objects.append("fire hydrant")
            elif "bicycle" in challenge_text.lower():
                target_objects.append("bicycle")
            elif "traffic light" in challenge_text.lower():
                target_objects.append("traffic light")
            elif "crosswalk" in challenge_text.lower() or "crossing" in challenge_text.lower():
                target_objects.append("crosswalk")
            
            print(f"Looking for objects: {target_objects}")
            
            # Get all image tiles
            tiles = challenge_frame.locator('table.rc-imageselect-table td')
            
            # Wait a bit to make sure images are loaded
            page.wait_for_timeout(2000)
            
            # Simplified image selection logic - in a real-world scenario,
            # you would use image recognition or a more sophisticated approach
            # For this example, I'll select tiles that are likely to contain the target
            
            # Get tile count
            tile_count = tiles.count()
            print(f"Found {tile_count} tiles")
            
            if "bus" in target_objects:
                # For bus detection, let's select tiles that might contain buses
                # In a real implementation, this would use image recognition
                # For this demo, we'll select a pattern of tiles that might work
                selected_tiles = [0, 2, 3, 8]  # Example pattern for buses
                
                for idx in selected_tiles:
                    if idx < tile_count:
                        print(f"Clicking tile {idx}")
                        tiles.nth(idx).click()
                        page.wait_for_timeout(300)  # Small delay between clicks
            
            # Wait for verification button to become enabled
            verify_button = challenge_frame.locator('#recaptcha-verify-button')
            verify_button.wait_for(state='enabled', timeout=2000)
            
            # Click verify
            print("Clicking verify button")
            verify_button.click()
            
            # Wait for result
            page.wait_for_timeout(5000)
            
            # Check if we need to continue solving
            new_challenge = challenge_frame.locator('.rc-imageselect-desc').count() > 0
            if new_challenge:
                print("Need to solve more challenges")
                self._solve_image_challenge(page, challenge_frame)
                
        except Exception as e:
            print(f"Error solving image challenge: {str(e)}")
            # Continue anyway as the user might need to solve manually

# API Endpoints
@app.route('/createTask', methods=['POST'])
@validate_api_key
def create_task():
    try:
        # Use default URL and sitekey from environment variables
        url = DEFAULT_RECAPTCHA_URL
        sitekey = DEFAULT_RECAPTCHA_SITEKEY
        
        task_id = str(uuid.uuid4())
        
        # Store new task with processing status
        task_store[task_id] = {
            'status': 'processing',
            'created': datetime.now(),
            'clientKey': request.json.get('clientKey')
        }
        
        # Process task in background
        solver = RecaptchaSolver()
        request_queue.add(task_id, solver.solve, url, sitekey)
        
        # Return taskId immediately
        return jsonify({
            'success': 1,
            'taskId': task_id
        })
    
    except Exception as e:
        return jsonify({
            'success': 0,
            'message': str(e)
        }), 500

@app.route('/createTaskUrl', methods=['POST'])
@validate_api_key
def create_task_url():
    try:
        data = request.get_json()
        url = data.get('url')
        sitekey = data.get('sitekey')
        
        if not url or not sitekey:
            return jsonify({
                'success': 0,
                'message': "URL and sitekey are required"
            }), 400
        
        task_id = str(uuid.uuid4())
        
        # Store new task with processing status
        task_store[task_id] = {
            'status': 'processing',
            'created': datetime.now(),
            'clientKey': data.get('clientKey')
        }
        
        # Process task in background
        solver = RecaptchaSolver()
        request_queue.add(task_id, solver.solve, url, sitekey)
        
        # Return taskId immediately
        return jsonify({
            'success': 1,
            'taskId': task_id
        })
    
    except Exception as e:
        return jsonify({
            'success': 0,
            'message': str(e)
        }), 500

@app.route('/getTaskResult', methods=['POST'])
@validate_api_key
def get_task_result():
    try:
        data = request.get_json()
        task_id = data.get('taskId')
        
        if not task_id:
            return jsonify({
                'success': 0,
                'message': "taskId is required"
            }), 400
        
        task = task_store.get(task_id)
        
        if not task:
            return jsonify({
                'success': 0,
                'message': "Task not found"
            }), 404
        
        # Clean up old tasks (optional)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        if task['created'] < one_hour_ago:
            task_store.pop(task_id, None)
            return jsonify({
                'success': 0,
                'message': "Task expired"
            }), 404
        
        # Return result based on status
        if task['status'] == 'processing':
            return jsonify({
                'success': 1,
                'message': "processing"
            })
        
        elif task['status'] == 'ready':
            return jsonify({
                'success': 1,
                'message': "ready",
                'gRecaptchaResponse': task.get('gRecaptchaResponse')
            })
        
        elif task['status'] == 'failed':
            return jsonify({
                'success': 0,
                'message': "failed",
                'error': task.get('error', 'Unknown error')
            })
        
        else:
            return jsonify({
                'success': 0,
                'message': "Unknown task status"
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': 0,
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'taskCount': len(task_store),
        'queueLength': request_queue.queue.qsize()
    })

# Task cleanup
def cleanup_tasks():
    while True:
        try:
            one_hour_ago = datetime.now() - timedelta(hours=1)
            cleaned_count = 0
            
            for task_id in list(task_store.keys()):
                task = task_store.get(task_id)
                if task and task['created'] < one_hour_ago:
                    task_store.pop(task_id, None)
                    cleaned_count += 1
            
            if cleaned_count > 0:
                print(f"Cleaned up {cleaned_count} expired tasks")
                
            time.sleep(15 * 60)  # Run every 15 minutes
        except Exception as e:
            print(f"Error in cleanup_tasks: {str(e)}")

# Start cleanup thread
cleanup_thread = Thread(target=cleanup_tasks, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    print(f"Server running on port {PORT}")
    print(f"Health check available at: http://0.0.0.0:{PORT}/health")
    app.run(host='0.0.0.0', port=PORT, debug=os.getenv('FLASK_ENV') == 'development')