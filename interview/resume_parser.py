# interview/resume_parser.py

import pdfplumber
import docx
import os
import re
from PIL import Image
import io

import spacy
from spacy.matcher import PhraseMatcher

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: pytesseract not installed. OCR for scanned PDFs will not be available.")

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading 'en_core_web_sm' model. This might take a moment...")
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")


def extract_text_from_resume(file_path):
    _, extension = os.path.splitext(file_path)
    text = ""
    
    try:
        if extension == '.pdf':
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text
                
                if not text.strip() and OCR_AVAILABLE:
                    print("PDF appears to be scanned. Attempting OCR...")
                    text = extract_text_with_ocr(file_path)
            return text
        
        elif extension == '.docx':
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text
            
        else:
            return f"Unsupported file type: {extension}"
            
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return f"Error reading file: {e}"


def extract_text_with_ocr(pdf_path):
    if not OCR_AVAILABLE:
        return "OCR not available. Install pytesseract to process scanned PDFs."
    
    text = ""
    try:
        import pdf2image
        images = pdf2image.convert_from_path(pdf_path)
        
        for i, image in enumerate(images):
            page_text = pytesseract.image_to_string(image)
            text += page_text + "\n"
            print(f"OCR processed page {i+1}/{len(images)}")
        
        return text
    except ImportError:
        return "pdf2image not installed. Cannot perform OCR on scanned PDFs."
    except Exception as e:
        print(f"OCR error: {e}")
        return f"OCR failed: {e}"


def extract_contact_info(text):
    contact_info = {
        'email': None,
        'phone': None,
        'linkedin': None,
        'github': None
    }
    
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    if emails:
        contact_info['email'] = emails[0]
    
    phone_patterns = [
        r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\d{10}'
    ]
    for pattern in phone_patterns:
        phones = re.findall(pattern, text)
        if phones:
            contact_info['phone'] = phones[0]
            break
    
    linkedin_pattern = r'linkedin\.com/in/[\w-]+'
    linkedin = re.findall(linkedin_pattern, text.lower())
    if linkedin:
        contact_info['linkedin'] = linkedin[0]
    
    github_pattern = r'github\.com/[\w-]+'
    github = re.findall(github_pattern, text.lower())
    if github:
        contact_info['github'] = github[0]
    
    return contact_info


def extract_experience_years(text):
    doc = nlp(text)
    total_years = 0
    experience_entries = []
    
    year_patterns = [
        r'(\d{1,2})\+?\s*years?\s+(?:of\s+)?experience',
        r'experience[:\s]+(\d{1,2})\+?\s*years?',
        r'(\d{4})\s*[-–—]\s*(\d{4}|present|current)',
        r'(\d{4})\s*[-–—]\s*(\d{4})'
    ]
    
    for pattern in year_patterns:
        matches = re.finditer(pattern, text.lower())
        for match in matches:
            if len(match.groups()) == 1:
                years = int(match.group(1))
                total_years = max(total_years, years)
            elif len(match.groups()) == 2:
                start_year = int(match.group(1))
                end_year_str = match.group(2)
                if end_year_str in ['present', 'current']:
                    end_year = 2024
                else:
                    end_year = int(end_year_str)
                years = end_year - start_year
                if 0 < years < 50:
                    experience_entries.append(years)
    
    if experience_entries:
        total_years = sum(experience_entries)
    
    return {
        'total_years': total_years,
        'experience_entries': experience_entries
    }


def extract_education(text):
    education_info = {
        'degrees': [],
        'institutions': [],
        'fields': []
    }
    
    degree_patterns = [
        r'\b(Ph\.?D\.?|PhD|Doctorate)\b',
        r'\b(Master[\'s]*|M\.?S\.?|M\.?A\.?|MBA|M\.?Tech\.?|M\.?E\.?)\b',
        r'\b(Bachelor[\'s]*|B\.?S\.?|B\.?A\.?|B\.?Tech\.?|B\.?E\.?)\b',
        r'\b(Associate[\'s]*|A\.?S\.?|A\.?A\.?)\b',
        r'\b(Diploma|Certificate)\b'
    ]
    
    for pattern in degree_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        education_info['degrees'].extend(matches)
    
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "ORG":
            org_text = ent.text.lower()
            if any(keyword in org_text for keyword in ['university', 'college', 'institute', 'school', 'iit', 'mit']):
                education_info['institutions'].append(ent.text)
    
    field_keywords = [
        'computer science', 'engineering', 'mathematics', 'physics', 
        'business', 'management', 'data science', 'artificial intelligence',
        'information technology', 'software engineering', 'electrical',
        'mechanical', 'civil', 'chemical', 'biotechnology'
    ]
    
    text_lower = text.lower()
    for field in field_keywords:
        if field in text_lower:
            education_info['fields'].append(field.title())
    
    return education_info


def categorize_skills(skills_list):
    SKILL_CATEGORIES = {
        "Core CS": ["Algorithms", "C", "C++", "C#", "F#", "Compiler Design", "Concurrency", "Computer Networks", "Data Structures", "Distributed Systems", "DNS", "Dynamic Programming", "Functional Programming", "Go", "Golang", "Greedy Algorithms", "Graphs", "Hash Tables", "Heaps", "HTTP", "HTTPS", "Java", "JavaScript", "Kernel", "Kotlin", "Linux", "Linked Lists", "Load Balancing", "Memory Management", "Microservices", "Multithreading", "Object-Oriented Programming", "OOPS", "Operating Systems", "OS", "Parallelism", "Perl", "PHP", "Processes", "Python", "R", "Recursion", "Ruby", "Rust", "Scala", "Searching", "Shell", "Bash", "Sockets", "Sorting", "SQL", "Swift", "System Design", "TCP/IP", "Threads", "Trees", "Unix", "Virtualization", "Windows", "Actor Model", "Assembly", "A* Search", "B-Tree", "Elixir", "Emacs", "Erlang", "Vim", "Vi", "Design Patterns", "Breadth-First Search", "BFS", "Depth-First Search", "DFS", "Dijkstra's Algorithm", "Trie", "OSI Model", "MATLAB", "File Systems", "Garbage Collection", "RPC", "Remote Procedure Call", "Scheduling", "Semaphores", "Mutex", "Deadlock", "Lisp", "Haskell", "Clojure", "Scheme", "Prolog", "Imperative Programming", "Declarative Programming", "Logic Programming", "Solidity", "Smart Contracts", "Cryptography", "Bit manipulation", "POSIX", "Message Queues", "Queuing Theory", "Finite Automata", "Turing Machine"],
        "Web Dev": [".NET", ".NET Core", "Angular", "Angular.js", "ASP.NET", "Bootstrap", "Client-Side Rendering", "CSR", "CSS", "Cypress", "Django", "DOM", "ES6", "Express.js", "FastAPI", "Flask", "Gatsby", "GraphQL", "gRPC", "HTML", "JavaScript", "JS", "jQuery", "Jest", "Jinja", "JWT", "JSON Web Token", "Laravel", "LESS", "Material UI", "MUI", "Meteor", "Next.js", "Nginx", "Node.js", "Nuxt.js", "OAuth", "PHP", "Playwright", "PostCSS", "React", "React.js", "React Testing Library", "Redux", "Remix", "REST API", "RESTful APIs", "Ruby on Rails", "Rails", "SASS", "Selenium", "Server-Side Rendering", "SSR", "SolidJS", "Spring", "Spring Boot", "Static Site Generation", "SSG", "Styled-Components", "Svelte", "SvelteKit", "Tailwind", "Tailwind CSS", "TypeScript", "TS", "Vite", "Vitest", "Vue.js", "WebAssembly", "WASM", "WebRTC", "WebSockets", "Webpack", "Accessibility", "a11y", "Apache", "Apache Tomcat", "Tomcat", "Astro", "Babel", "Backbone.js", "CakePHP", "CDN", "CGI", "Chakra UI", "Chrome Extensions", "CodeIgniter", "Cookies", "D3.js", "Ember.js", "EJS", "ESLint", "Fastify", "Handlebars", "Hapi", "Hono", "HTTP/2", "HTTP/3", "IIS", "Koa", "Local Storage", "Session Storage", "Micro-frontends", "Monorepo", "NestJS", "Phoenix", "Polymer", "Preact", "Prettier", "Progressive Web App", "PWA", "Puppeteer", "Qwik", "Serverless Functions", "Service Workers", "Socket.io", "Storybook", "Symfony", "Three.js", "Turborepo", "WebGL", "Wordpress", "Yii"],
        "AI/ML/DS": ["A/B Testing", "Accuracy", "AI", "Analytics", "ARIMA", "Artificial Intelligence", "BERT", "Business Intelligence", "BI", "CatBoost", "Classification", "Clustering", "CNN", "Computer Vision", "CV", "Convolutional Neural Networks", "Data Cleaning", "Data Mining", "Data Science", "Data Visualization", "Data Wrangling", "Deep Learning", "DL", "EDA", "Exploratory Data Analysis", "F1-score", "Feature Engineering", "GAN", "Generative AI", "GenAI", "Generative Adversarial Networks", "GPT", "Hugging Face", "Hyperparameter Tuning", "Image Segmentation", "JAX", "Jupyter", "Keras", "LangChain", "LightGBM", "LlamaIndex", "Large Language Models", "LLM", "Machine Learning", "ML", "Matplotlib", "Metrics", "MLOps", "Model Evaluation", "Model Training", "Natural Language Processing", "NLP", "Neural Networks", "NN", "NLTK", "NumPy", "Object Detection", "OpenAI", "OpenCV", "Overfitting", "Pandas", "Power BI", "Precision", "PyTorch", "Recall", "Regression", "Reinforcement Learning", "RL", "Retrieval-Augmented Generation", "RAG", "RNN", "Recurrent Neural Networks", "Scikit-learn", "SciPy", "Seaborn", "Sentiment Analysis", "spaCy", "SQL", "Statsmodels", "Supervised Learning", "Tableau", "TensorFlow", "Tokenization", "Transfer Learning", "Transformers", "Underfitting", "Unsupervised Learning", "Vector Database", "XGBoost", "YOLO", "Activation Function", "Adam", "Autoencoder", "AutoML", "Backpropagation", "Bayesian", "Bias-Variance Tradeoff", "BigQuery", "ChromaDB", "Data Augmentation", "Data Governance", "Data Lake", "Data Warehouse", "Decision Trees", "Embeddings", "ETL", "Fine-tuning", "Gradio", "Gradient Descent", "Hidden Markov Model", "HMM", "ImageNet", "K-Means", "KNN", "Kubeflow", "Linear Regression", "Logistic Regression", "Looker", "Loss Function", "LSTM", "MILVUS", "MLflow", "Naive Bayes", "Pinecone", "Plotly", "Qdrant", "Quantization", "Random Forest", "ResNet", "Semi-Supervised Learning", "Streamlit", "Support Vector Machine", "SVM", "t-SNE", "VGG", "Weaviate"],
        "Cyber Security": ["Access Control", "Application Security", "AppSec", "Attack Vectors", "Authentication", "Authorization", "Blue Team", "Brute Force", "Burp Suite", "CASB", "Cloud Security", "Compliance", "Cryptography", "Cross-Site Scripting", "XSS", "CSPM", "CWPP", "Cybersecurity", "Data Encryption", "Data Loss Prevention", "DLP", "Denial of Service", "DoS", "Distributed Denial of Service", "DDoS", "DevSecOps", "Ethical Hacking", "Firewalls", "GDPR", "Hashcat", "HIPAA", "Identity and Access Management", "IAM", "Incident Response", "IR", "Information Security", "Intrusion Detection System", "IDS", "Intrusion Prevention System", "IPS", "ISO 27001", "John the Ripper", "Malware Analysis", "Man-in-the-Middle", "MITM", "Metasploit", "Multi-Factor Authentication", "MFA", "Nessus", "Network Security", "Nmap", "NIST", "OWASP", "PCI-DSS", "Penetration Testing", "Pen Test", "Phishing", "Purple Team", "Ransomware", "Red Team", "Risk Assessment", "SIEM", "Security Information and Event Management", "Snort", "SOC", "Security Operations Center", "SOC 2", "Social Engineering", "SOAR", "Splunk", "SQL Injection", "Threat Intelligence", "Threat Modeling", "Vulnerability Assessment", "Wireshark", "Zero Trust", "Zero Trust Architecture", "ZTA", "AES", "Antivirus", "BCP", "Business Continuity Planning", "CISSP", "CMMC", "CompTIA Security+", "Security+", "CSA", "CISA", "CEH", "Cross-Site Request Forgery", "CSRF", "Directory Traversal", "Digital Forensics", "DRP", "Disaster Recovery Plan", "EASM", "Endpoint Security", "FedRAMP", "Forensics", "Ghidra", "GVM", "Homomorphic Encryption", "Honeypot", "Insecure Deserialization", "Key Management", "LDAP", "Mobile Security", "Okta", "OpenVAS", "OSINT", "PKI", "Public Key Infrastructure", "Principle of Least Privilege", "Radare2", "Reverse Engineering", "RSA", "SAST", "DAST", "IAST", "Sandboxing", "Security Audits", "Shodan", "SSO", "Single Sign-On", "SSL", "TLS", "TTPs", "WAF", "Web Application Firewall", "XDR", "Zero-Knowledge Proof", "ZKP"],
        "DB/Cloud/DevOps": ["Agile", "Amazon Web Services", "AWS", "Ansible", "Apache Kafka", "Kafka", "Azure", "Azure DevOps", "Azure Functions", "Bitbucket", "Cassandra", "Chef", "CI/CD", "CircleCI", "Cloud Computing", "CloudFormation", "Configuration Management", "Containerization", "Continuous Deployment", "Continuous Integration", "Datadog", "DB2", "DigitalOcean", "Docker", "DynamoDB", "EC2", "Elasticsearch", "ELK Stack", "Firebase", "Firestore", "GCP", "Google Cloud", "Git", "GitHub", "GitLab", "GitLab CI", "Gitflow", "Google Cloud Functions", "Grafana", "Heroku", "IaC", "Infrastructure as Code", "IAM", "Jenkins", "Jira", "Kanban", "Kubernetes", "K8s", "Lambda", "AWS Lambda", "Linode", "MariaDB", "Microsoft SQL Server", "SQL Server", "MongoDB", "Monitoring", "MySQL", "NoSQL", "Observability", "Oracle", "Oracle SQL", "Packer", "PostgreSQL", "Postgres", "Prometheus", "Pulumi", "Puppet", "RabbitMQ", "RDS", "Redis", "S3", "Scrum", "Serverless", "Site Reliability Engineering", "SRE", "Snowflake", "SQLite", "Terraform", "Travis CI", "Vagrant", "VPC", "Version Control", "Active Directory", "ArgoCD", "AKS", "Azure Kubernetes Service", "BASH Scripting", "ClickHouse", "Cloudflare", "Cloud Run", "CloudWatch", "CockroachDB", "Couchbase", "CouchDB", "DataDog", "Databricks", "EKS", "Elastic Kubernetes Service", "ECS", "FinOps", "Flux", "GKE", "Google Kubernetes Engine", "GitOps", "GitHub Actions", "Helm", "InfluxDB", "Istio", "Linkerd", "Memcached", "New Relic", "Oracle Cloud", "OCI", "PlanetScale", "Powershell", "Rancher", "Redshift", "Route 53", "SaltStack", "Service Mesh", "SLI", "SLO", "Spinnaker", "Supabase", "TeamCity", "Terraform Cloud", "TimescaleDB", "Vault", "HashiCorp Vault", "VMware", "Vercel"],
        "Mobile Development": ["Mobile Development", "iOS", "Android", "Swift", "SwiftUI", "UIKit", "Objective-C", "ObjC", "Kotlin", "Java", "Android SDK", "Android NDK", "Xcode", "Android Studio", "React Native", "Flutter", "Dart", "Xamarin", ".NET MAUI", "NativeScript", "Ionic", "Capacitor", "Apache Cordova", "Cordova", "PhoneGap", "Core Data", "SQLite", "Realm", "Firebase", "Fastlane", "App Store Connect", "Google Play Console", "TestFlight", "APK", "App Bundle", "AAB", "CocoaPods", "Swift Package Manager", "SPM", "Gradle", "ARKit", "Core ML", "ML Kit", "Jetpack Compose", "Jetpack", "LiveData", "ViewModel", "Room", "RxJava", "RxKotlin", "RxSwift", "Combine", "Grand Central Dispatch", "GCD", "Coroutines", "Kotlin Coroutines", "AlamoFire", "Kingfisher", "Push Notifications", "APNS", "FCM", "WidgetKit", "WatchOS", "TVOS", "Accessibility", "App Clips", "Core Animation", "Core Audio", "Core Graphics", "Core Location", "MapKit", "Metal", "SceneKit", "SpriteKit", "KMM", "Kotlin Multiplatform", "Ktor", "LeakCanary", "ProGuard", "R8", "Android App Bundle", "Material Design", "ConstraintLayout", "Fragments", "Intents", "Services", "Broadcast Receivers", "Content Providers", "Dagger", "Hilt", "Koin", "MVI", "MVVM", "MVC", "VIPER", "Redux", "MobX", "BLoC", "GetX", "Provider", "Riverpod", "SwiftData", "Viper", "Texture", "AsyncDisplayKit", "SnapKit", "Vapor", "Perfect", "Kitura", "Bugsnag", "Sentry", "Crashlytics"],
        "Game Development": ["Game Development", "Game Dev", "Unreal Engine", "UE4", "UE5", "Unity", "Unity3D", "C#", "C++", "Blueprints", "UnrealScript", "CryEngine", "Godot", "Lumberyard", "GameMaker", "RPG Maker", "Twine", "Blender", "Maya", "3ds Max", "ZBrush", "Autodesk", "Cinema 4D", "Houdini", "Modo", "Substance Painter", "Substance Designer", "Quixel", "Megascans", "HLSL", "GLSL", "Shader", "DirectX", "OpenGL", "Vulkan", "Metal", "WebGL", "Physics Engine", "Havok", "PhysX", "Bullet", "Box2D", "Gameplay Programming", "Game AI", "Level Design", "Game Design", "3D Modeling", "Texturing", "Rigging", "Animation", "Real-Time Rendering", "Ray Tracing", "Game Physics", "Multiplayer", "Networking", "VR", "Virtual Reality", "AR", "Augmented Reality", "Mixed Reality", "MR", "XR", "Steam", "Epic Games Store", "Mobile Games", "Console Development", "2D", "3D", "AAA", "Asset Pipeline", "Artificial Intelligence", "AI", "Asset Store", "Audio Programming", "Cocos2d-x", "Compute Shaders", "DOTS", "ECS", "Entity Component System", "Game Feel", "Juice", "Game Loop", "Game State Management", "Gaffer", "GIMP", "Krita", "Level Editor", "Lighting", "LOD", "Level of Detail", "Materials", "NavMesh", "Pathfinding", "A*", "Particle Systems", "Photon", "PlayFab", "Procedural Generation", "PBR", "Physically Based Rendering", "Pygame", "Render Pipeline", "URP", "HDRP", "Scriptable Objects", "Shaders", "Sprite", "Tilemap", "UI/UX", "User Interface", "Vector Math", "Quaternion", "VFX", "Visual Effects", "Wwise", "FMOD"],
        "Design/UI/UX": ["UI", "User Interface", "UX", "User Experience", "UI/UX", "Figma", "Sketch", "Adobe XD", "InVision", "Axure", "Balsamiq", "Zeplin", "Framer", "Principle", "Photoshop", "Illustrator", "After Effects", "Adobe Creative Suite", "Interaction Design", "IxD", "User Research", "User Testing", "Usability", "Usability Testing", "Accessibility", "a11y", "WCAG", "Wireframing", "Prototyping", "Mockups", "High-Fidelity", "Hi-Fi", "Low-Fidelity", "Lo-Fi", "Design Systems", "Atomic Design", "User Personas", "Personas", "Journey Mapping", "User Flows", "Empathy Maps", "Heuristic Evaluation", "Card Sorting", "Information Architecture", "IA", "Visual Design", "Typography", "Color Theory", "Responsive Design", "Mobile-First Design", "Human-Computer Interaction", "HCI", "Storyboarding", "A/B Testing", "User-Centered Design", "UCD", "Design Thinking", "Marvel", "Abstract", "User Interviews", "Surveys", "Affinity Diagram", "Canva", "CorelDRAW", "Webflow", "Maze", "UserZoom", "Hotjar"],
        "Embedded Systems/IoT": ["Embedded Systems", "Embedded C", "Embedded C++", "Internet of Things", "IoT", "M2M", "Machine-to-Machine", "Real-Time Operating System", "RTOS", "FreeRTOS", "Zephyr", "VxWorks", "QNX", "Firmware", "Microcontroller", "MCU", "Microprocessor", "MPU", "SoC", "System-on-a-Chip", "FPGA", "ASIC", "Arduino", "Raspberry Pi", "ESP8266", "ESP32", "STM32", "ARM", "ARM Cortex", "RISC-V", "PIC", "BeagleBone", "Jetson Nano", "MQTT", "CoAP", "AMQP", "SPI", "I2C", "UART", "CAN Bus", "Modbus", "Zigbee", "Z-Wave", "Bluetooth", "BLE", "LoRa", "LoRaWAN", "6LoWPAN", "VHDL", "Verilog", "SystemVerilog", "LabVIEW", "MATLAB", "Simulink", "Keil", "IAR", "Eclipse IoT", "PlatformIO", "Yocto", "Buildroot", "Sensors", "Actuators", "GPIO", "ADC", "DAC", "PWM", "JTAG", "SWD", "OTA", "Over-the-Air", "Edge Computing", "IIoT", "Industrial IoT", "TinyML", "Bare Metal"]
    }
    
    categorized = {}
    skills_lower = [s.lower() for s in skills_list]
    
    for category, category_skills in SKILL_CATEGORIES.items():
        matched = []
        for skill in category_skills:
            if skill.lower() in skills_lower:
                matched.append(skill)
        if matched:
            categorized[category] = matched
    
    return categorized

def extract_skills(text):
    SKILL_CATEGORIES = {
        "Core CS": ["Algorithms", "Big O Notation", "C", "C++", "C#", "F#", "Compiler Design", "Concurrency", "Computer Networks", "Data Structures", "Distributed Systems", "DNS", "Dynamic Programming", "Functional Programming", "Go", "Golang", "Greedy Algorithms", "Graphs", "Hash Tables", "Heaps", "HTTP", "HTTPS", "Java", "JavaScript", "Kernel", "Kotlin", "Linux", "Linked Lists", "Load Balancing", "Memory Management", "Microservices", "Multithreading", "Object-Oriented Programming", "OOP", "Operating Systems", "OS", "Parallelism", "Perl", "PHP", "Processes", "Python", "R", "Recursion", "Ruby", "Rust", "Scala", "Searching", "Shell", "Bash", "Sockets", "Sorting", "SQL", "Swift", "System Design", "TCP/IP", "Threads", "Trees", "Unix", "Virtualization", "Windows", "Actor Model", "Assembly", "A* Search", "B-Tree", "Elixir", "Emacs", "Erlang", "Vim", "Vi", "Design Patterns", "Breadth-First Search", "BFS", "Depth-First Search", "DFS", "Dijkstra's Algorithm", "Trie", "OSI Model", "MATLAB", "File Systems", "Garbage Collection", "RPC", "Remote Procedure Call", "Scheduling", "Semaphores", "Mutex", "Deadlock", "Lisp", "Haskell", "Clojure", "Scheme", "Prolog", "Imperative Programming", "Declarative Programming", "Logic Programming", "Solidity", "Smart Contracts", "Cryptography", "Bit manipulation", "POSIX", "Message Queues", "Queuing Theory", "Finite Automata", "Turing Machine"],
        "Web Dev": [".NET", ".NET Core", "Angular", "Angular.js", "ASP.NET", "Bootstrap", "Client-Side Rendering", "CSR", "CSS", "Cypress", "Django", "DOM", "ES6", "Express.js", "FastAPI", "Flask", "Gatsby", "GraphQL", "gRPC", "HTML", "JavaScript", "JS", "jQuery", "Jest", "Jinja", "JWT", "JSON Web Token", "Laravel", "LESS", "Material UI", "MUI", "Meteor", "Next.js", "Nginx", "Node.js", "Nuxt.js", "OAuth", "PHP", "Playwright", "PostCSS", "React", "React.js", "React Testing Library", "Redux", "Remix", "REST API", "RESTful APIs", "Ruby on Rails", "Rails", "SASS", "Selenium", "Server-Side Rendering", "SSR", "SolidJS", "Spring", "Spring Boot", "Static Site Generation", "SSG", "Styled-Components", "Svelte", "SvelteKit", "Tailwind", "Tailwind CSS", "TypeScript", "TS", "Vite", "Vitest", "Vue.js", "WebAssembly", "WASM", "WebRTC", "WebSockets", "Webpack", "Accessibility", "a11y", "Apache", "Apache Tomcat", "Tomcat", "Astro", "Babel", "Backbone.js", "CakePHP", "CDN", "CGI", "Chakra UI", "Chrome Extensions", "CodeIgniter", "Cookies", "D3.js", "Ember.js", "EJS", "ESLint", "Fastify", "Handlebars", "Hapi", "Hono", "HTTP/2", "HTTP/3", "IIS", "Koa", "Local Storage", "Session Storage", "Micro-frontends", "Monorepo", "NestJS", "Phoenix", "Polymer", "Preact", "Prettier", "Progressive Web App", "PWA", "Puppeteer", "Qwik", "Serverless Functions", "Service Workers", "Socket.io", "Storybook", "Symfony", "Three.js", "Turborepo", "WebGL", "Wordpress", "Yii"],
        "AI/ML/DS": ["A/B Testing", "Accuracy", "AI", "Analytics", "ARIMA", "Artificial Intelligence", "BERT", "Business Intelligence", "BI", "CatBoost", "Classification", "Clustering", "CNN", "Computer Vision", "CV", "Convolutional Neural Networks", "Data Cleaning", "Data Mining", "Data Science", "Data Visualization", "Data Wrangling", "Deep Learning", "DL", "EDA", "Exploratory Data Analysis", "F1-score", "Feature Engineering", "GAN", "Generative AI", "GenAI", "Generative Adversarial Networks", "GPT", "Hugging Face", "Hyperparameter Tuning", "Image Segmentation", "JAX", "Jupyter", "Keras", "LangChain", "LightGBM", "LlamaIndex", "Large Language Models", "LLM", "Machine Learning", "ML", "Matplotlib", "Metrics", "MLOps", "Model Evaluation", "Model Training", "Natural Language Processing", "NLP", "Neural Networks", "NN", "NLTK", "NumPy", "Object Detection", "OpenAI", "OpenCV", "Overfitting", "Pandas", "Power BI", "Precision", "PyTorch", "Recall", "Regression", "Reinforcement Learning", "RL", "Retrieval-Augmented Generation", "RAG", "RNN", "Recurrent Neural Networks", "Scikit-learn", "SciPy", "Seaborn", "Sentiment Analysis", "spaCy", "SQL", "Statsmodels", "Supervised Learning", "Tableau", "TensorFlow", "Tokenization", "Transfer Learning", "Transformers", "Underfitting", "Unsupervised Learning", "Vector Database", "XGBoost", "YOLO", "Activation Function", "Adam", "Autoencoder", "AutoML", "Backpropagation", "Bayesian", "Bias-Variance Tradeoff", "BigQuery", "ChromaDB", "Data Augmentation", "Data Governance", "Data Lake", "Data Warehouse", "Decision Trees", "Embeddings", "ETL", "Fine-tuning", "Gradio", "Gradient Descent", "Hidden Markov Model", "HMM", "ImageNet", "K-Means", "KNN", "Kubeflow", "Linear Regression", "Logistic Regression", "Looker", "Loss Function", "LSTM", "MILVUS", "MLflow", "Naive Bayes", "Pinecone", "Plotly", "Qdrant", "Quantization", "Random Forest", "ResNet", "Semi-Supervised Learning", "Streamlit", "Support Vector Machine", "SVM", "t-SNE", "VGG", "Weaviate"],
        "Cyber Security": ["Access Control", "Application Security", "AppSec", "Attack Vectors", "Authentication", "Authorization", "Blue Team", "Brute Force", "Burp Suite", "CASB", "Cloud Security", "Compliance", "Cryptography", "Cross-Site Scripting", "XSS", "CSPM", "CWPP", "Cybersecurity", "Data Encryption", "Data Loss Prevention", "DLP", "Denial of Service", "DoS", "Distributed Denial of Service", "DDoS", "DevSecOps", "Ethical Hacking", "Firewalls", "GDPR", "Hashcat", "HIPAA", "Identity and Access Management", "IAM", "Incident Response", "IR", "Information Security", "Intrusion Detection System", "IDS", "Intrusion Prevention System", "IPS", "ISO 27001", "John the Ripper", "Malware Analysis", "Man-in-the-Middle", "MITM", "Metasploit", "Multi-Factor Authentication", "MFA", "Nessus", "Network Security", "Nmap", "NIST", "OWASP", "PCI-DSS", "Penetration Testing", "Pen Test", "Phishing", "Purple Team", "Ransomware", "Red Team", "Risk Assessment", "SIEM", "Security Information and Event Management", "Snort", "SOC", "Security Operations Center", "SOC 2", "Social Engineering", "SOAR", "Splunk", "SQL Injection", "Threat Intelligence", "Threat Modeling", "Vulnerability Assessment", "Wireshark", "Zero Trust", "Zero Trust Architecture", "ZTA", "AES", "Antivirus", "BCP", "Business Continuity Planning", "CISSP", "CMMC", "CompTIA Security+", "Security+", "CSA", "CISA", "CEH", "Cross-Site Request Forgery", "CSRF", "Directory Traversal", "Digital Forensics", "DRP", "Disaster Recovery Plan", "EASM", "Endpoint Security", "FedRAMP", "Forensics", "Ghidra", "GVM", "Homomorphic Encryption", "Honeypot", "Insecure Deserialization", "Key Management", "LDAP", "Mobile Security", "Okta", "OpenVAS", "OSINT", "PKI", "Public Key Infrastructure", "Principle of Least Privilege", "Radare2", "Reverse Engineering", "RSA", "SAST", "DAST", "IAST", "Sandboxing", "Security Audits", "Shodan", "SSO", "Single Sign-On", "SSL", "TLS", "TTPs", "WAF", "Web Application Firewall", "XDR", "Zero-Knowledge Proof", "ZKP"],
        "DB/Cloud/DevOps": ["Agile", "Amazon Web Services", "AWS", "Ansible", "Apache Kafka", "Kafka", "Azure", "Azure DevOps", "Azure Functions", "Bitbucket", "Cassandra", "Chef", "CI/CD", "CircleCI", "Cloud Computing", "CloudFormation", "Configuration Management", "Containerization", "Continuous Deployment", "Continuous Integration", "Datadog", "DB2", "DigitalOcean", "Docker", "DynamoDB", "EC2", "Elasticsearch", "ELK Stack", "Firebase", "Firestore", "GCP", "Google Cloud", "Git", "GitHub", "GitLab", "GitLab CI", "Gitflow", "Google Cloud Functions", "Grafana", "Heroku", "IaC", "Infrastructure as Code", "IAM", "Jenkins", "Jira", "Kanban", "Kubernetes", "K8s", "Lambda", "AWS Lambda", "Linode", "MariaDB", "Microsoft SQL Server", "SQL Server", "MongoDB", "Monitoring", "MySQL", "NoSQL", "Observability", "Oracle", "Oracle SQL", "Packer", "PostgreSQL", "Postgres", "Prometheus", "Pulumi", "Puppet", "RabbitMQ", "RDS", "Redis", "S3", "Scrum", "Serverless", "Site Reliability Engineering", "SRE", "Snowflake", "SQLite", "Terraform", "Travis CI", "Vagrant", "VPC", "Version Control", "Active Directory", "ArgoCD", "AKS", "Azure Kubernetes Service", "BASH Scripting", "ClickHouse", "Cloudflare", "Cloud Run", "CloudWatch", "CockroachDB", "Couchbase", "CouchDB", "DataDog", "Databricks", "EKS", "Elastic Kubernetes Service", "ECS", "FinOps", "Flux", "GKE", "Google Kubernetes Engine", "GitOps", "GitHub Actions", "Helm", "InfluxDB", "Istio", "Linkerd", "Memcached", "New Relic", "Oracle Cloud", "OCI", "PlanetScale", "Powershell", "Rancher", "Redshift", "Route 53", "SaltStack", "Service Mesh", "SLI", "SLO", "Spinnaker", "Supabase", "TeamCity", "Terraform Cloud", "TimescaleDB", "Vault", "HashiCorp Vault", "VMware", "Vercel"],
        "Mobile Development": ["Mobile Development", "iOS", "Android", "Swift", "SwiftUI", "UIKit", "Objective-C", "ObjC", "Kotlin", "Java", "Android SDK", "Android NDK", "Xcode", "Android Studio", "React Native", "Flutter", "Dart", "Xamarin", ".NET MAUI", "NativeScript", "Ionic", "Capacitor", "Apache Cordova", "Cordova", "PhoneGap", "Core Data", "SQLite", "Realm", "Firebase", "Fastlane", "App Store Connect", "Google Play Console", "TestFlight", "APK", "App Bundle", "AAB", "CocoaPods", "Swift Package Manager", "SPM", "Gradle", "ARKit", "Core ML", "ML Kit", "Jetpack Compose", "Jetpack", "LiveData", "ViewModel", "Room", "RxJava", "RxKotlin", "RxSwift", "Combine", "Grand Central Dispatch", "GCD", "Coroutines", "Kotlin Coroutines", "AlamoFire", "Kingfisher", "Push Notifications", "APNS", "FCM", "WidgetKit", "WatchOS", "TVOS", "Accessibility", "App Clips", "Core Animation", "Core Audio", "Core Graphics", "Core Location", "MapKit", "Metal", "SceneKit", "SpriteKit", "KMM", "Kotlin Multiplatform", "Ktor", "LeakCanary", "ProGuard", "R8", "Android App Bundle", "Material Design", "ConstraintLayout", "Fragments", "Intents", "Services", "Broadcast Receivers", "Content Providers", "Dagger", "Hilt", "Koin", "MVI", "MVVM", "MVC", "VIPER", "Redux", "MobX", "BLoC", "GetX", "Provider", "Riverpod", "SwiftData", "Viper", "Texture", "AsyncDisplayKit", "SnapKit", "Vapor", "Perfect", "Kitura", "Bugsnag", "Sentry", "Crashlytics"],
        "Game Development": ["Game Development", "Game Dev", "Unreal Engine", "UE4", "UE5", "Unity", "Unity3D", "C#", "C++", "Blueprints", "UnrealScript", "CryEngine", "Godot", "Lumberyard", "GameMaker", "RPG Maker", "Twine", "Blender", "Maya", "3ds Max", "ZBrush", "Autodesk", "Cinema 4D", "Houdini", "Modo", "Substance Painter", "Substance Designer", "Quixel", "Megascans", "HLSL", "GLSL", "Shader", "DirectX", "OpenGL", "Vulkan", "Metal", "WebGL", "Physics Engine", "Havok", "PhysX", "Bullet", "Box2D", "Gameplay Programming", "Game AI", "Level Design", "Game Design", "3D Modeling", "Texturing", "Rigging", "Animation", "Real-Time Rendering", "Ray Tracing", "Game Physics", "Multiplayer", "Networking", "VR", "Virtual Reality", "AR", "Augmented Reality", "Mixed Reality", "MR", "XR", "Steam", "Epic Games Store", "Mobile Games", "Console Development", "2D", "3D", "AAA", "Asset Pipeline", "Artificial Intelligence", "AI", "Asset Store", "Audio Programming", "Cocos2d-x", "Compute Shaders", "DOTS", "ECS", "Entity Component System", "Game Feel", "Juice", "Game Loop", "Game State Management", "Gaffer", "GIMP", "Krita", "Level Editor", "Lighting", "LOD", "Level of Detail", "Materials", "NavMesh", "Pathfinding", "A*", "Particle Systems", "Photon", "PlayFab", "Procedural Generation", "PBR", "Physically Based Rendering", "Pygame", "Render Pipeline", "URP", "HDRP", "Scriptable Objects", "Shaders", "Sprite", "Tilemap", "UI/UX", "User Interface", "Vector Math", "Quaternion", "VFX", "Visual Effects", "Wwise", "FMOD"],
        "Design/UI/UX": ["UI", "User Interface", "UX", "User Experience", "UI/UX", "Figma", "Sketch", "Adobe XD", "InVision", "Axure", "Balsamiq", "Zeplin", "Framer", "Principle", "Photoshop", "Illustrator", "After Effects", "Adobe Creative Suite", "Interaction Design", "IxD", "User Research", "User Testing", "Usability", "Usability Testing", "Accessibility", "a11y", "WCAG", "Wireframing", "Prototyping", "Mockups", "High-Fidelity", "Hi-Fi", "Low-Fidelity", "Lo-Fi", "Design Systems", "Atomic Design", "User Personas", "Personas", "Journey Mapping", "User Flows", "Empathy Maps", "Heuristic Evaluation", "Card Sorting", "Information Architecture", "IA", "Visual Design", "Typography", "Color Theory", "Responsive Design", "Mobile-First Design", "Human-Computer Interaction", "HCI", "Storyboarding", "A/B Testing", "User-Centered Design", "UCD", "Design Thinking", "Marvel", "Abstract", "User Interviews", "Surveys", "Affinity Diagram", "Canva", "CorelDRAW", "Webflow", "Maze", "UserZoom", "Hotjar"],
        "Embedded Systems/IoT": ["Embedded Systems", "Embedded C", "Embedded C++", "Internet of Things", "IoT", "M2M", "Machine-to-Machine", "Real-Time Operating System", "RTOS", "FreeRTOS", "Zephyr", "VxWorks", "QNX", "Firmware", "Microcontroller", "MCU", "Microprocessor", "MPU", "SoC", "System-on-a-Chip", "FPGA", "ASIC", "Arduino", "Raspberry Pi", "ESP8266", "ESP32", "STM32", "ARM", "ARM Cortex", "RISC-V", "PIC", "BeagleBone", "Jetson Nano", "MQTT", "CoAP", "AMQP", "SPI", "I2C", "UART", "CAN Bus", "Modbus", "Zigbee", "Z-Wave", "Bluetooth", "BLE", "LoRa", "LoRaWAN", "6LoWPAN", "VHDL", "Verilog", "SystemVerilog", "LabVIEW", "MATLAB", "Simulink", "Keil", "IAR", "Eclipse IoT", "PlatformIO", "Yocto", "Buildroot", "Sensors", "Actuators", "GPIO", "ADC", "DAC", "PWM", "JTAG", "SWD", "OTA", "Over-the-Air", "Edge Computing", "IIoT", "Industrial IoT", "TinyML", "Bare Metal"]
    }
    
    SKILL_LIST = []
    for category, skills in SKILL_CATEGORIES.items():
        SKILL_LIST.extend([skill.lower() for skill in skills])
    
    doc = nlp(text.lower())
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    skill_patterns = [nlp.make_doc(skill) for skill in SKILL_LIST]
    matcher.add("SKILL_MATCHER", skill_patterns)
    matches = matcher(doc)
    
    found_skills = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        found_skills.add(span.text)
        
    return list(found_skills)


def parse_resume_complete(file_path):
    text = extract_text_from_resume(file_path)
    
    if text.startswith("Error") or text.startswith("Unsupported"):
        return {'error': text}
    
    skills = extract_skills(text)
    contact_info = extract_contact_info(text)
    experience = extract_experience_years(text)
    education = extract_education(text)
    skill_categories = categorize_skills(skills)
    
    return {
        'text': text,
        'skills': skills,
        'skill_categories': skill_categories,
        'contact_info': contact_info,
        'experience': experience,
        'education': education
    }
