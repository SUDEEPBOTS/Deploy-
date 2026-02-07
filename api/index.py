from flask import Flask, render_template, request, jsonify
import requests
import os
from pymongo import MongoClient

app = Flask(__name__, template_folder='../templates')

# --- CONFIGURATION ---
ADMIN_PASS = "sudeep123"

# MongoDB Connection (Vercel ke Environment Variable se lega)
# Agar local run kar raha hai toh direct string daal sakta hai, par Vercel pe Env Var best hai.
MONGO_URI = os.environ.get("MONGO_URI")

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

# --- ADD ACCOUNT (Saves to MongoDB) ---
@app.route('/api/add_key', methods=['POST'])
def add_key():
    data = request.json
    if data.get('password') != ADMIN_PASS:
        return jsonify({"error": "Wrong Password!"}), 403
    
    new_key = data.get('key')
    
    # Check if key already exists
    if accounts_col.find_one({"api_key": new_key}):
        return jsonify({"error": "Key already exists!"}), 400

    if new_key:
        # Save to DB
        accounts_col.insert_one({"api_key": new_key})
        count = accounts_col.count_documents({})
        return jsonify({"message": f"Saved to DB! Total Accounts: {count}"})
    
    return jsonify({"error": "Invalid Key"}), 400

# --- DEPLOY LOGIC (Fetches from MongoDB) ---
@app.route('/api/deploy', methods=['POST'])
def deploy():
    data = request.json
    repo = data.get('repo')
    env_vars_text = data.get('env')
    
    # Database se saari keys nikalo
    all_accounts = list(accounts_col.find({}))
    
    if not all_accounts:
        return jsonify({"status": "error", "message": "No Accounts found in Database!"})

    # Convert Env Text to Render JSON
    env_vars = []
    if env_vars_text:
        for line in env_vars_text.split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                env_vars.append({"key": k.strip(), "value": v.strip()})

    # --- LOAD BALANCER ---
    selected_key = None
    
    # Har saved account ko check karo
    for acc in all_accounts:
        key = acc['api_key']
        headers = {"Authorization": f"Bearer {key}"}
        
        try:
            # Render API se pucho: "Kitne services hain?"
            res = requests.get("https://api.render.com/v1/services?limit=20", headers=headers)
            if res.status_code == 200:
                services = res.json()
                # Agar 2 se kam hain, toh ye account select kar lo
                if len(services) < 2:
                    selected_key = key
                    break
        except:
            continue
    
    if not selected_key:
        return jsonify({"status": "error", "message": "All Accounts are FULL (2/2)!"})

    # --- DEPLOY REQUEST ---
    deploy_url = "https://api.render.com/v1/services"
    payload = {
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
        return jsonify({"status": "error", "message": response.text})

if __name__ == '__main__':
    app.run()
    
