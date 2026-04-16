import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

doc_ref = db.document("靜宜資管/sakura")
doc = doc_ref.get()
result = doc.to_dict()
print(f"姓名:{result['name']}的老師，研究室在{result['lab']}，電子郵件為{result['mail']}")