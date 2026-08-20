import pandas as pd
from rapidfuzz import process, fuzz
import json

class FoppaOrderMatcher:
    def __init__(self, schablone_path, archive_path, confidence_threshold=85.0):
        """
        Initializes the matching engine by loading the masterdata.
        """
        # Load the CSV files
        self.schablone_df = pd.read_csv(schablone_path)
        self.archive_df = pd.read_csv(archive_path)
        self.confidence_threshold = confidence_threshold
        
    def _find_best_match(self, query_text, choices_df):
        """
        Matches extracted unstructured text against both German and Italian descriptions.
        """
        # Create dictionaries mapping index to descriptions for bilingual fuzzy matching
        dict_de = choices_df['DescriptionGerman'].dropna().to_dict()
        dict_it = choices_df['DescriptionItalian'].dropna().to_dict()
        
        # Perform token sort ratio matching (good for out-of-order words like "Käse Bianco" vs "Bianco Käse")
        match_de = process.extractOne(query_text, dict_de, scorer=fuzz.token_sort_ratio)
        match_it = process.extractOne(query_text, dict_it, scorer=fuzz.token_sort_ratio)
        
        best_match, best_score, best_idx = None, 0, -1
        
        # Compare German and Italian match scores and take the highest
        if match_de and match_de[1] > best_score:
            best_match, best_score, best_idx = match_de
        if match_it and match_it[1] > best_score:
            best_match, best_score, best_idx = match_it
            
        if best_idx != -1:
            # Retrieve the full row data from the DataFrame using the winning index
            row = choices_df.loc[best_idx]
            return row, best_score
        
        return None, 0

    def process_order_line(self, customer_code, extracted_text, extracted_quantity):
        """
        The core 2-tier matching pipeline for a single order line.
        """
        # Define the base JSON structure for the ERP system
        result = {
            "OriginalText": extracted_text,
            "ExtractedQuantity": extracted_quantity,
            "MatchedItemCode": None,
            "MatchedDescription": None,
            "UnitOfMeasurement": None,
            "ConfidenceScore": 0,
            "Source": "None",
            "NeedsHumanReview": True,
            "Alternatives": []
        }
        
        # --- TIER 1: Customer Template (Schablone) ---
        # Filter for this specific customer and EXCLUDE blocked items (Blocked == 1)
        customer_template = self.schablone_df[
            (self.schablone_df['Customercode'] == customer_code) & 
            (self.schablone_df['Blocked'] == 0)
        ]
        
        if not customer_template.empty:
            best_row, score = self._find_best_match(extracted_text, customer_template)
            
            if score >= self.confidence_threshold:
                # If score is highly confident, lock it in as an automatic match
                result.update({
                    "MatchedItemCode": best_row['ItemCode'],
                    "MatchedDescription": best_row['DescriptionGerman'], 
                    "UnitOfMeasurement": best_row['UnitofMeasurement'],
                    "ConfidenceScore": round(score, 2),
                    "Source": "CustomerTemplate",
                    "NeedsHumanReview": False # Can potentially bypass human review
                })
                return result
            else:
                # If below threshold, save the best template guess as an alternative
                if best_row is not None:
                     result["Alternatives"].append({
                         "ItemCode": best_row['ItemCode'],
                         "Description": best_row['DescriptionGerman'],
                         "Score": round(score, 2),
                         "Source": "CustomerTemplate"
                     })
                
        # --- TIER 2: Global Catalog Fallback (CompleteItemArchive) ---
        # Only reached if Tier 1 had no high-confidence match
        best_row_global, score_global = self._find_best_match(extracted_text, self.archive_df)
        
        if best_row_global is not None:
            result.update({
                "MatchedItemCode": best_row_global['ItemCode'],
                "MatchedDescription": best_row_global['DescriptionGerman'],
                "UnitOfMeasurement": best_row_global['UnitofMeasurement'],
                "ConfidenceScore": round(score_global, 2),
                "Source": "GlobalCatalogFallback",
                "NeedsHumanReview": True # Fallbacks should always be verified by a human
            })
            
        return result

# ==========================================
# Example Usage Simulator
# ==========================================
if __name__ == "__main__":
    # In reality, you'd pass the paths to your extracted CSV files here
    # matcher = FoppaOrderMatcher('Schablone.csv', 'CompleteItemArchive.csv')
    
    # Simulating data from your file B0244_0001.txt ("Hoi bitte tuischmo 5 schweinskaiserteile ohne deckl...")
    customer = "B0244"
    ai_extracted_text = "schweinskaiserteile ohne deckl" 
    ai_extracted_qty = 5
    
    # matched_json = matcher.process_order_line(customer, ai_extracted_text, ai_extracted_qty)
    # print(json.dumps(matched_json, indent=4))