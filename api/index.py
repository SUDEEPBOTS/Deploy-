from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__, template_folder='../templates')

# Admin Password
ADMIN_PASS = "sudeep123"

# Temporary Storage for API Keys (Note: Vercel serverless reset hota hai, 
# permanent ke liye MongoDB lagana padega baad mein)
RENDER_KEYS = [
    # "rnd_ExampleKey1............",
]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/api/add_key', methods=['POST'])
def add_key():
    data = request.json
    if data.get('password') != ADMIN_PASS:
        return jsonify({"error": "Wrong Password!"}), 403
    
    new_key = data.get('key')
    if new_key and new_key not in RENDER_KEYS:
        RENDER_KEYS.append(new_key)
        return jsonify({"message": f"Key Added! Total Accounts: {len(RENDER_KEYS)}"})
    return jsonify({"error": "Invalid or Duplicate Key"}), 400

@app.route('/api/deploy', methods=['POST'])
def deploy():
    data = request.json
    repo = data.get('repo')
    env_vars_text = data.get('env')
    
    if not RENDER_KEYS:
        return jsonify({"status": "error", "message": "No Render Accounts configured!"})

    # Convert Env Text to Render JSON format
    env_vars = []
    for line in env_vars_text.split('\n'):
        if '=' in line:
            k, v = line.split('=', 1)
            env_vars.append({"key": k.strip(), "value": v.strip()})

    # --- LOAD BALANCER LOGIC ---
    selected_key = None
    
    for key in RENDER_KEYS:
        headers = {"Authorization": f"Bearer {key}"}
        # Check current services count
        try:
            res = requests.get("https://api.render.com/v1/services?limit=20", headers=headers)
            if res.status_code == 200:
                services = res.json()
                # Check if account has less than 2 services (Modify limit as needed)
                if len(services) < 2:
                    selected_key = key
                    break
        except:
            continue
    
    if not selected_key:
        return jsonify({"status": "error", "message": "All Accounts are FULL!"})

    # --- DEPLOYMENT ---
    deploy_url = "https://api.render.com/v1/services"
    payload = {
        "type": "web_service",
        "serviceDetails": {
            "name": f"bot-{len(env_vars)}", # Random name logic
            "repo": repo,
            "env": "python",
            "plan": "free",
            "region": "oregon",
            "buildCommand": "pip install -r requirements.txt",
            "startCommand": "python3 main.py",
            "envVars": env_vars
        }
    }
    
    headers = {"Authorization": f"Bearer {selected_key}", "Content-Type": "application/json"}
    response = requests.post(deploy_url, json=payload, headers=headers)
    
    if response.status_code == 201:
        data = response.json()
        return jsonify({
            "status": "success", 
            "url": data['serviceUrl'], 
            "id": data['id'],
            "account_used": f"...{selected_key[-5:]}"
        })
    else:
        return jsonify({"status": "error", "message": response.text})

# Vercel needs this
if __name__ == '__main__':
    app.run()
  
