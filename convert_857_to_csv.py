import csv

FIELDS = [
    ("type", 1),                    # סוג רשומה: B
    ("record_id", 9),              # מזהה רשומה
    ("payer_id", 9),               # ת"ז משלם
    ("payment_id", 15),           # מספר תשלום/חשבונית/שורה
    ("employee_seq", 3),           # רצף
    ("unknown1", 11),              # שדה לא מזוהה
    ("sum_total_agorot", 13),      # סכום כולל באגורות
    ("name", 40),                  # שם מקבל תשלום (כנראה בעברית)
    ("date_from", 8),              # תאריך התחלה (YYYYMMDD)
    ("date_to", 8),                # תאריך סיום
    ("payment_code", 6),           # קוד תשלום
    ("payment_type", 1),           # סוג תשלום (1=רגיל, 2=נוסף)
    ("currency", 3),               # מטבע (USD/NIS)
    ("sum_payment", 14),           # סכום תשלום עיקרי באגורות
    ("sum_tax", 14),               # ניכוי מס באגורות
    ("sum_exempt", 14),            # סכום פטור
    ("sum_extra", 14),             # סכום נוסף כלשהו
    ("sum_deducted", 14),          # סכום מנוכה נוסף
    ("date_exec", 8),              # תאריך הפקה
]

def parse_fixed_width(line, fields):
    pos = 0
    row = {}
    for name, width in fields:
        value = line[pos:pos + width]
        row[name] = value.strip()
        pos += width
    return row

with open('BKMVDATA.txt', 'r', encoding='windows-1255') as infile, \
     open('mkvdata.csv', 'w', newline='', encoding='utf-8') as outfile:

    writer = csv.DictWriter(outfile, fieldnames=[f[0] for f in FIELDS])
    writer.writeheader()

    for line in infile:
        if line.startswith('B'):
            row = parse_fixed_width(line, FIELDS)
            print (row)
            # המרה לשקלים
            row['sum_total_agorot'] = int(row['sum_total_agorot']) / 100
            row['sum_payment'] = int(row['sum_payment']) / 100
            row['sum_tax'] = int(row['sum_tax']) / 100
            writer.writerow(row)

print("✅ ההמרה הושלמה: mkvdata.csv")
