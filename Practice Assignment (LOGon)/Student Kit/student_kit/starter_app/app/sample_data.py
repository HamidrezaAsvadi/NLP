from __future__ import annotations

from .schemas import Product


CATALOG = [
    Product(
        code="FPN1T",
        description="FRUCHTPUREE MANGO 1kg GEFR. FRUITIERE",
        unit="BEG",
        package_size="1 kg",
        aliases=["mango puree", "mango piree", "fruchtpueree mango"],
    ),
    Product(
        code="OEG25",
        description="SONNENBLUMENOEL 10l BIG CHEF",
        unit="KAN",
        package_size="10 l",
        aliases=["sonnenblumenoel big chef", "sunflower oil big chef", "oel big chef"],
    ),
    Product(
        code="EI35F",
        description="EIER SPEZIAL 180er OX (L) 63-73g",
        unit="KRT",
        package_size="180 pcs",
        aliases=["180er eier l", "eggs l", "large eggs", "eier spezial l"],
    ),
    Product(
        code="KART02",
        description="KARTOFFELSALAT 2kg HAUSGEMACHT",
        unit="KRT",
        package_size="2 kg",
        aliases=["kartoffelsalat", "potato salad", "patate insalata"],
    ),
    Product(
        code="TOM10",
        description="TOMATENSAUCE PASSIERT 10kg",
        unit="EIM",
        package_size="10 kg",
        aliases=["tomatensauce", "passata", "tomato sauce"],
    ),
]


CUSTOMER_HISTORY = {
    "CUST-DEMO": ["FPN1T", "OEG25", "EI35F"],
    "CUST-PIZZA": ["TOM10", "OEG25"],
    "CUST-CATERING": ["KART02", "EI35F", "FPN1T"],
}


DEMO_TEXT = """Mango puree 1
Sonnenblumenoel Big Chef 2
180er Eier L 4
morgen liefern"""
