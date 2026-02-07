from flask import Flask, render_template, request, jsonify
import requests
import os
from pymongo import MongoClient

app = Flask(__name__, template_folder='../templates')

# --- CONFIGURATION ---
ADMIN_PASS = "sudeep123"
MONGO_URI = os.environ.get("MONGO_URI") # Vercel Env Var

# Database Connection
try:
    client = MongoClient(MONGO_URI)
    db = client.get_database("render_deployer")
    accounts_col = db.get_collection("accounts")
    print("✅ MongoDB Connected!")
except Exception as e:
    print(f"❌ Database Error: {e}")
    accounts_col = None

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
    if accounts_col.find_one({"api_key": new_key}):
        return jsonify({"error": "Key already exists!"}), 400

    if new_key:
        accounts_col.insert_one({"api_key": new_key})
        return jsonify({"message": "Saved to DB!"})
    
    return jsonify({"error": "Invalid Key"}), 400

# --- FIXED DEPLOY LOGIC ---
@app.route('/api/deploy', methods=['POST'])
def deploy():
    data = request.json
    repo = data.get('repo')
    env_vars_text = data.get('env')
    
    all_accounts = list(accounts_col.find({}))
    if not all_accounts:
        return jsonify({"status": "error", "message": "No Accounts in Database!"})

    # Env Vars Parsing
    env_vars = []
    if env_vars_text:
        for line in env_vars_text.split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                env_vars.append({"key": k.strip(), "value": v.strip()})

    selected_key = None
    owner_id = None  # Variable to store Owner ID

    # --- LOAD BALANCER & OWNER CHECK ---
    for acc in all_accounts:
        key = acc['api_key']
        headers = {"Authorization": f"Bearer {key}"}
        
        try:
            # Step 1: Check Services Count
            res = requests.get("https://api.render.com/v1/services?limit=20", headers=headers)
            if res.status_code == 200:
                services = res.json()
                if len(services) < 5:  # Limit 2 se badha kar 5 kar sakte ho agar chahiye
                    
                    # Step 2: FETCH OWNER ID (Ye zaroori hai!)
                    owner_res = requests.get("https://api.render.com/v1/owners", headers=headers)
                    if owner_res.status_code == 200:
                        owners = owner_res.json()
                        # Pehla owner utha lo (usually user khud hota hai)
                        owner_id = owners[0]['id']
                        selected_key = key
                        break
        except:
            continue
    
    if not selected_key or not owner_id:
        return jsonify({"status": "error", "message": "All Accounts FULL or Owner ID Error!"})

    # --- DEPLOY REQUEST (With Owner ID) ---
    deploy_url = "https://api.render.com/v1/services"
    
    payload = {
        "ownerId": owner_id,  # <--- YAHAN FIX HUA HAI
        "type": "web_service",
        "serviceDetails": {
            "name": f"bot-{len(env_vars)}", 
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
            "account_used": f"...{selected_key[-5:]}"
        })
    else:
        # Error detail print karo debug ke liye
        return jsonify({"status": "error", "message": response.text})

if __name__ == '__main__':
    app.run()
    
