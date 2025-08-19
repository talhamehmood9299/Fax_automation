import json
import re
from datetime import datetime
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MODEL_NAME = "gpt-4.1"

class DocumentInformation(BaseModel):
    patient_name: str
    date_of_birth: str
    provider_name: str


def openai(messages, response_text):
    if response_text:
        completion = client.chat.completions.parse(
            model=MODEL_NAME,
            messages=messages,
            response_format=response_text,
        )
    else:
        completion = client.chat.completions.parse(
            model=MODEL_NAME,
            messages=messages,
        )
    return completion.choices[0].message


def try_parse_dob(raw_dob):
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(raw_dob, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception:
            continue
    if re.fullmatch(r'(0[1-9]|1[0-2])/([0][1-9]|[12][0-9]|3[01])/\d{4}', raw_dob):
        return raw_dob
    return None

def extract_information(document):
    system_prompt = """
    You are a clinical document extractor. Extract the following from the provided medical fax file:

    - patient_name: The patient's full name, as shown in the document.
    - date_of_birth: The patient's date of birth, in mm/dd/yyyy format. Convert if necessary.
    - provider_name: The referring, ordering, or "To:" provider—the person to whom this fax was sent, not the author, interpreter, or signer of the report. If the document contains a "To:" section, extract the name found there. If no "To:" is present, use the provider explicitly listed as the ordering/referring physician or simply Physician:. Do NOT extract any names from the end of the document, signature, or interpreting provider sections.

    Instructions:
    - Always return all three fields, using an empty string for any that are missing.
    - Do NOT include provider credentials (e.g., "MD", "DO", "APN", "PA-C"). Only return the provider's name.
    - Respond ONLY with a valid JSON object.
    """
    response = openai(
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': document}
        ],
        response_text=DocumentInformation
    )
    # Handle both response types
    resp_content = response.content if hasattr(response, 'content') else response
    data = json.loads(resp_content)

    # Optionally validate & parse date here (using your try_parse_dob)
    date_of_birth = try_parse_dob(data.get("date_of_birth", ""))
    patient_name = data.get("patient_name", "")
    provider_name = data.get("provider_name", "")

    return date_of_birth, patient_name, provider_name

def find_doctype(document: str) -> str:
    doc_type_list = [
        "Lab/imaging Orders",
        "Principle Illness Navigation (Pin)",
        "Cologuard",
        "Payment Receipt",
        "Physical Therapy",
        "Care Plan",
        "Home Care",
        "Encounter",
        "Bills",
        "Bhi",
        "Pcm",
        "Colonoscopy/endoscopy",
        "Ccm",
        "Mammogram",
        "Outgoings",
        "Test",
        "Forms",
        "Medical Records Request",
        "Letters",
        "Prior Authorization",
        "Medical Marijuana",
        "Medical Records",
        "Insurance Card, Id",
        "Sleep Study",
        "Pharmacy",
        "Consult",
        "Insurance",
        "Prescription",
        "Immunization Records",
        "Referral",
        "Hospital",
        "Radiology",
        "Labs",
        "Patient Documents"
    ]

    # System prompt for the LLM
    system_prompt = f"""
    You are a medical document classifier.
    From the list below, select the single most appropriate document type for the provided document content.

    --- Document Type Definitions ---
    1. Consult: Includes consultation notes, progress notes, evaluation notes, and encounter notes received from a doctor’s office, clinic, or hospital (Outpatient). These documents reflect the provider’s assessment and care plan during a specific visit.
    2. Hospital: Includes comprehensive documentation from hospital encounters, inpatient and outpatient. This may include Emergency/ED notes, History & Physical (H&P), Discharge Summaries, After Visit Summaries, Summary of Care, and related ED or outpatient orders. These records capture evaluation, treatment, and discharge planning.
    3. Labs: Laboratory results consist of diagnostic tests performed on specimens (blood, urine, stool, fluids, tissues) analyzed in a laboratory setting.
    4. Radiology: Imaging diagnostic studies including X-ray, CT, MRI, Ultrasound, etc. Results include findings/report impressions.
    5. Tests: Diagnostic test reports not classified as Laboratory or Radiology (e.g., EKG/ECG, Echocardiogram, NCS, EMG, Holter, Stress Test, 6 Min walk, etc).
    6. Prior Authorization: Documents confirming or updating a prior authorization (PA) request, usually for medication or a radiological/imaging service.
    7. Medical Records: Typically received in response to request (or unsolicited), these documents often include multiple clinical items grouped together: radiology reports, consults, labs, ED notes, etc.
    8. Medical Records Request: Requests for medical records, sometimes with authorization forms, from various sources (offices, hospitals, labs, insurance, legal, agencies, etc).
    9. Forms: Documents requiring physician review/signature, often needing return fax, such as plan of care, surgical clearance, FMLA, supply requests, etc.
    10. Referrals: Patient referral forms, usually with encounter note, demographics, insurance, referral source/destination, reason, diagnosis codes, etc.
    11. Pharmacy: Requests from pharmacies for refills, new prescriptions, or alternate meds, with patient and medication details.
    12. Sleep Study: Results of Polysomnography (sleep study), giving findings for sleep patterns, breathing, and other observations.
    13. Cologuard: Documents related to the Cologuard test for colorectal cancer screening (results, notifications, etc).
    14. Colonoscopy/Endoscopy: Includes Colonoscopy, Endoscopy, GI pathology, Upper GI Endoscopy, biopsy results, delivered after the procedure.
    15. Mammogram: Breast imaging and related documents—diagnostic/screening mammograms, ultrasounds, breast biopsies, breast MRI, etc.
    16. Immunization Records: Records of vaccinations given to a patient, including dates, vaccine names, and location.
    17. Physical Therapy: Plans/treatment recommendations from physical therapy or rehab centers, sent for physician review.
    18. Home Care: Reports such as Episode Summary/Discharge Summary from home health centers, detailing care delivered at home and patient status/goals.
    19. Letters: Brief, time-sensitive letters from providers or facilities, usually reporting changes, urgent issues, or updates.
    20. Insurance Card, ID: Insurance membership cards or similar, to update or verify a patient’s insurance.
    21. Insurance: Insurance documents (excluding medication/radiology PAs), including approvals, denials, reductions, or coverage updates.
    22. Patient Documents: Non-clinical papers tied to the patient, such as police reports, licenses, proof of residence, ESA forms, photos, or legal forms affecting care.
    23. Care Plan: Care management summaries (often from insurers), goals/recommendations/risks/contacts for care coordination.
    --- End Definitions ---

    Your options are:
    {', '.join(doc_type_list)}

    Only return the type EXACTLY as it appears in the list above.
    """

    response = openai(
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': document}
        ],
        response_text=None
    )
    doctype = response.content.strip() if hasattr(response, 'content') else str(response).strip()
    return doctype


def find_sub_doctype(document: str) -> str:
    system_prompt = """
    You are a document extractor. From the provided document, extract ONLY the sender name (clinic, lab, hospital, organization, or entity that sent or originated the document).
    Return only the sender name as a string.
    Do not include any explanations or extra text.
    """
    response = openai(
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': document}
        ],
        response_text=None
    )
    final_response = response.content.strip() if hasattr(response, 'content') else str(response).strip()
    return final_response

def generate_document_comments(document: str) -> str:
    system_prompt = """
    You are an assistant that provides concise, clinically relevant comments or summaries for medical documents.
    Review the provided document and generate either:
    - 2 to 4 bullet points summarizing key findings, recommendations, or next steps, OR
    - a short paragraph (2 to 3 lines) summarizing the document's most important details.
    Be clear, avoid unnecessary details, and keep the comments actionable and relevant to clinical care.
    Do not copy large sections from the original document.
    """
    response = openai(
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': document}
        ],
        response_text=None
    )
    final_response = response.content.strip() if hasattr(response, 'content') else str(response).strip()
    return final_response


