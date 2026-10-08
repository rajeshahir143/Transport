# Radhe Radhe Developer — PDF DO / Builty / Bill prototype

Workflow:
1. Upload a GMDC Delivery Order PDF.
2. PDF details are extracted and a DO is created.
3. Builty Entry shows Pending DOs.
4. Enter the actual loaded truck quantity. That quantity is deducted from the DO remaining quantity.
5. Bill (Material) Entry shows Pending Builty records.
6. Select multiple Builty records and create one Bill.
7. Billed Builty records disappear from Pending Builty.

Run:
    pip install -r requirements.txt
    python main.py

The supplied sample PDF can be used to test the import.
