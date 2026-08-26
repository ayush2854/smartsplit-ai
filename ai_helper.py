import time
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def categorize_expense(description, amount):
    try:
        prompt = f"""
        You are an expense categorization assistant.
        Categorize this expense into exactly ONE of these categories:
        Food, Transport, Accommodation, Entertainment, Shopping, Medical, Utilities, Other

        Expense: "{description}" for amount Rs.{amount}

        Reply with ONLY the category name. Nothing else.
        """
        time.sleep(1)  # Small delay to respect rate limits
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )
        return response.text.strip()
    except Exception:
        description_lower = description.lower()
        if any(word in description_lower for word in ['food', 'lunch', 'dinner', 'breakfast', 'restaurant', 'eat']):
            return 'Food'
        elif any(word in description_lower for word in ['hotel', 'stay', 'room', 'hostel']):
            return 'Accommodation'
        elif any(word in description_lower for word in ['taxi', 'cab', 'bus', 'train', 'flight', 'petrol']):
            return 'Transport'
        else:
            return 'Other'

def get_spending_insights(expenses, group_name):
    if not expenses:
        return "No expenses added yet. Start adding expenses to get AI insights."

    expense_list = "\n".join([
        f"- {e['description']}: Rs.{e['amount']} (paid by {e['paid_by']}, category: {e['category']})"
        for e in expenses
    ])

    prompt = f"""
    You are a smart financial advisor analyzing trip expenses for a group called "{group_name}".

    Here are the expenses:
    {expense_list}

    Give a friendly, helpful analysis in 4-5 sentences covering:
    1. Which category had the highest spending
    2. Who paid the most overall
    3. One practical money-saving tip for their next trip

    Keep the tone conversational and helpful, like a friend giving advice.
    """
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )
        return response.text.strip()
    except Exception:
        # Fallback: generate basic insights from the data directly
        total = sum(e['amount'] for e in expenses)
        category_totals = {}
        payer_totals = {}

        for e in expenses:
            category_totals[e['category']] = category_totals.get(e['category'], 0) + e['amount']
            payer_totals[e['paid_by']] = payer_totals.get(e['paid_by'], 0) + e['amount']

        top_category = max(category_totals, key=category_totals.get)
        top_payer = max(payer_totals, key=payer_totals.get)

        return (
            f"Your group spent a total of Rs.{total:.2f} on this trip. "
            f"The biggest spending category was {top_category} at Rs.{category_totals[top_category]:.2f}. "
            f"{top_payer} paid the most overall. "
            f"Tip: Try setting a daily budget before your next trip to avoid overspending on {top_category.lower()}."
        )

def calculate_settlements(expenses, members):
    member_list = [m.strip() for m in members.split(',')]
    balances = {member: 0 for member in member_list}

    total = sum(e['amount'] for e in expenses)
    if total == 0 or not member_list:
        return []

    share = total / len(member_list)

    for expense in expenses:
        paid_by = expense['paid_by'].strip()
        if paid_by in balances:
            balances[paid_by] += expense['amount']

    for member in member_list:
        balances[member] -= share

    settlements = []
    debtors = {k: -v for k, v in balances.items() if v < -0.01}
    creditors = {k: v for k, v in balances.items() if v > 0.01}

    for debtor, debt in debtors.items():
        for creditor, credit in creditors.items():
            if debt <= 0 or credit <= 0:
                continue
            amount = min(debt, credit)
            settlements.append({
                'from': debtor,
                'to': creditor,
                'amount': round(amount, 2)
            })
            debtors[debtor] -= amount
            creditors[creditor] -= amount

    return settlements

import base64
from PIL import Image
import io

def analyze_receipt(image_file):
    try:
        # Read image bytes directly
        image_bytes = image_file.read()
        
        # Open with Pillow for processing
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if too large
        max_size = (1024, 1024)
        img.thumbnail(max_size, Image.LANCZOS)
        
        # Save to buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        prompt = """
        Look at this image. It may be a receipt, bill, invoice, or photo of any purchase.
        
        Extract these details and respond in EXACTLY this format with no extra text:
        DESCRIPTION: [merchant name or what was purchased]
        AMOUNT: [final total as number only, no symbols]
        CATEGORY: [one of: Food, Transport, Accommodation, Entertainment, Shopping, Medical, Utilities, Other]
        
        If no receipt is visible, use your best guess from what you can see.
        """

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_data
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        text = response.text.strip()
        print("Gemini receipt response:", text)  # Debug log

        result = {
            'description': 'Unknown',
            'amount': 0,
            'category': 'Other'
        }

        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('DESCRIPTION:'):
                result['description'] = line.replace('DESCRIPTION:', '').strip()
            elif line.startswith('AMOUNT:'):
                try:
                    amount_str = line.replace('AMOUNT:', '').strip()
                    amount_str = ''.join(c for c in amount_str if c.isdigit() or c == '.')
                    result['amount'] = float(amount_str) if amount_str else 0
                except:
                    result['amount'] = 0
            elif line.startswith('CATEGORY:'):
                result['category'] = line.replace('CATEGORY:', '').strip()

        return result

    except Exception as e:
        print("Receipt scan error:", str(e))  # Debug log
        return {
            'description': 'Could not read receipt',
            'amount': 0,
            'category': 'Other',
            'error': str(e)
        }