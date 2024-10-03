import os
import streamlit as st
import pdfplumber
import docx
from fpdf import FPDF

# API configuration
import google.generativeai as genai

os.environ["GOOGLE_API_KEY"] = ''  # Add your API Key
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("models/gemini-1.5-pro")

# File handling configuration
UPLOAD_FOLDER = 'uploads/'
RESULTS_FOLDER = 'results/'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx'}

# Ensure folders exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(RESULTS_FOLDER):
    os.makedirs(RESULTS_FOLDER)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        with pdfplumber.open(file_path) as pdf:
            text = ''.join([page.extract_text() for page in pdf.pages])
        return text
    elif ext == 'docx':
        doc = docx.Document(file_path)
        text = ' '.join([para.text for para in doc.paragraphs])
        return text
    elif ext == 'txt':
        try:
            with open(file_path, 'r', encoding='utf-8') as file:  # Try UTF-8 first
                return file.read()
        except UnicodeDecodeError:
            # If it fails, try with a different encoding (ISO-8859-1 or Latin-1)
            with open(file_path, 'r', encoding='ISO-8859-1') as file:
                return file.read()
    return None


def Question_mcqs_generator(input_text, num_questions):
    prompt = f"""
    You are an AI assistant helping the user generate multiple-choice questions (MCQs) based on the following text:
    '{input_text}'
    Please generate {num_questions} MCQs from the text. Each question should have:
    - A clear question
    - Four answer options (labeled A, B, C, D)
    - The correct answer clearly indicated
    Format:
    ## MCQ
    Question: [question]
    A) [option A]
    B) [option B]
    C) [option C]
    D) [option D]
    Correct Answer: [correct option]
    """
    response = model.generate_content(prompt).text.strip()
    return response


def save_mcqs_to_file(mcqs, filename):
    results_path = os.path.join(RESULTS_FOLDER, filename)
    with open(results_path, 'w') as f:
        f.write(mcqs)
    return results_path


def create_pdf(mcqs, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            pdf.multi_cell(0, 10, mcq.strip())
            pdf.ln(5)  # Add a line break

    pdf_path = os.path.join(RESULTS_FOLDER, filename)
    pdf.output(pdf_path)
    return pdf_path


# Streamlit interface
st.title("MCQ Generator from Text")
st.write("Upload multiple files and generate multiple-choice questions (MCQs) automatically!")

# Allow multiple file uploads
uploaded_files = st.file_uploader("Upload your document(s) (PDF, TXT, DOCX):", type=['pdf', 'txt', 'docx'],
                                  accept_multiple_files=True)
num_questions = st.number_input("How many questions do you want?", min_value=1, step=1)

if uploaded_files:
    text = ""

    # Process each uploaded file
    for uploaded_file in uploaded_files:
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
        with open(file_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())

        # Extract text from each file
        extracted_text = extract_text_from_file(file_path)
        if extracted_text:
            text += extracted_text + " "  # Concatenate the text from all files

    if text.strip():  # Check if there is any text to generate MCQs
        with st.spinner("Generating MCQs..."):
            mcqs = Question_mcqs_generator(text, num_questions)

            # Save MCQs as a file (optional)
            txt_filename = f"generated_mcqs_combined.txt"
            pdf_filename = f"generated_mcqs_combined.pdf"
            save_mcqs_to_file(mcqs, txt_filename)
            create_pdf(mcqs, pdf_filename)

            st.success("MCQs generated successfully!")

            # Interactive Quiz Display
            st.write("Here are the generated MCQs:")

            score = 0
            total_questions = 0

            for idx, mcq in enumerate(mcqs.split("## MCQ")):
                if mcq.strip():
                    try:
                        question = mcq.split('A)')[0].strip()
                        option_a = mcq.split('A)')[1].split('B)')[0].strip()
                        option_b = mcq.split('B)')[1].split('C)')[0].strip()
                        option_c = mcq.split('C)')[1].split('D)')[0].strip()
                        option_d = mcq.split('D)')[1].split('Correct Answer:')[0].strip()
                        correct_answer = mcq.split('Correct Answer:')[1].strip()

                        # Interactive question using radio buttons (no default selected)
                        user_answer = st.radio(f"{idx + 1}. {question}",
                                               options=[f"A) {option_a}",
                                                        f"B) {option_b}",
                                                        f"C) {option_c}",
                                                        f"D) {option_d}"],
                                               key=f"question_{idx}",
                                               index=None)  # Ensure no default selection

                        # Show correct answer once the user selects
                        if user_answer:
                            if user_answer.split(')')[0] == correct_answer:
                                st.success(f"Correct! The answer is {correct_answer}.")
                                score += 1
                            else:
                                st.error(f"Wrong! The correct answer is {correct_answer}.")
                            total_questions += 1

                        st.markdown("---")

                    except (IndexError, ValueError) as e:
                        st.error(f"Error processing MCQ: {mcq}. Skipping this question.")
                        continue

            # Display total score
            if total_questions > 0:
                st.markdown(f"### Your score: {score}/{total_questions}")

            # Option to download generated MCQs
            st.write("Download options:")
            st.download_button(label="Download as TXT", data=open(os.path.join(RESULTS_FOLDER, txt_filename)).read(),
                               file_name=txt_filename)
            st.download_button(label="Download as PDF",
                               data=open(os.path.join(RESULTS_FOLDER, pdf_filename), 'rb').read(),
                               file_name=pdf_filename, mime='application/pdf')