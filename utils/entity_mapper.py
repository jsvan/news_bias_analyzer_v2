"""
Entity Mapping and Resolution Utilities

This module provides entity name normalization and mapping functionality
to handle duplicate entities with different names or types in the database.
"""

import re
from typing import List, Dict, Set, Optional, Tuple
from difflib import SequenceMatcher


class EntityMapper:
    """
    Maps entity names to canonical forms and finds duplicates/variants
    """
    
    def __init__(self):
        # Common entity name variations and mappings
        self.name_mappings = {
            # Countries - normalize different naming conventions
            'United States': ['USA', 'US', 'America', 'United States of America'],
            'United Kingdom': ['UK', 'Britain', 'Great Britain', 'England'],
            'Russia': ['Russian Federation', 'USSR', 'Soviet Union'],
            'China': ['People\'s Republic of China', 'PRC', 'Mainland China'],
            'Hong Kong': ['Hong Kong SAR', 'Hong Kong/China'],
            
            # People - handle common variations
            'Donald Trump': ['Trump', 'Donald J. Trump', 'President Trump', 'Donald John Trump'],
            'Vladimir Putin': ['Putin', 'Vladimir Vladimirovich Putin'],
            'Xi Jinping': ['Xi', 'President Xi'],
            'Joe Biden': ['Biden', 'Joseph Biden', 'President Biden', 'Joseph R. Biden'],
            
            # Organizations
            'European Union': ['EU', 'Europe'],
            'United Nations': ['UN', 'U.N.'],
            'NATO': ['North Atlantic Treaty Organization'],
            'WHO': ['World Health Organization'],
        }
        
        # Type mappings - different entity types that should be merged
        self.type_equivalents = {
            ('person', 'political_leader'): 'person',
            ('country', 'sovereign_state'): 'country',
            ('organization', 'company'): 'organization',
            ('location', 'place'): 'location',
        }
        
        # Build reverse mapping for quick lookups
        self.reverse_mappings = {}
        for canonical, variants in self.name_mappings.items():
            self.reverse_mappings[canonical.lower()] = canonical
            for variant in variants:
                self.reverse_mappings[variant.lower()] = canonical
    
    def normalize_entity_name(self, name: str) -> str:
        """
        Normalize an entity name to its canonical form
        """
        if not name:
            return name
            
        # Clean the name
        cleaned = self.clean_name(name)
        
        # Check for exact mapping
        canonical = self.reverse_mappings.get(cleaned.lower())
        if canonical:
            return canonical
            
        # Return cleaned version if no mapping found
        return cleaned
    
    def clean_name(self, name: str) -> str:
        """
        Clean entity name by removing extra whitespace, articles, etc.
        """
        if not name:
            return name
            
        # Remove extra whitespace
        cleaned = ' '.join(name.split())
        
        # Remove common prefixes/suffixes
        prefixes_to_remove = ['The ', 'President ', 'Prime Minister ', 'King ', 'Queen ']
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break
                
        return cleaned.strip()
    
    def find_entity_variants(self, target_name: str, entity_list: List[Dict]) -> List[Dict]:
        """
        Find all variants of an entity in the database
        
        Args:
            target_name: The entity name to search for
            entity_list: List of entity dictionaries with 'name' and 'type' fields
            
        Returns:
            List of matching entity variants
        """
        target_normalized = self.normalize_entity_name(target_name)
        variants = []
        
        for entity in entity_list:
            entity_name = entity.get('name', '') or entity.get('entity', '')
            if not entity_name:
                continue
                
            # Normalize the entity name
            normalized = self.normalize_entity_name(entity_name)
            
            # Check for exact match
            if normalized.lower() == target_normalized.lower():
                variants.append(entity)
                continue
                
            # Check for similarity
            similarity = self.calculate_similarity(target_normalized, normalized)
            if similarity > 0.85:  # High similarity threshold
                variants.append(entity)
        
        return variants
    
    def calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two entity names
        """
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
    
    def merge_entity_types(self, entities: List[Dict]) -> str:
        """
        Determine the best entity type when merging multiple entities
        """
        if not entities:
            return 'unknown'
            
        types = [e.get('type', e.get('entity_type', 'unknown')) for e in entities]
        type_counts = {}
        
        for entity_type in types:
            # Normalize type
            normalized_type = self.normalize_entity_type(entity_type)
            type_counts[normalized_type] = type_counts.get(normalized_type, 0) + 1
        
        # Return most common type
        return max(type_counts.items(), key=lambda x: x[1])[0]
    
    def normalize_entity_type(self, entity_type: str) -> str:
        """
        Normalize entity type using equivalence mappings
        """
        if not entity_type:
            return 'unknown'
            
        # Check for type equivalents
        for type_tuple, canonical_type in self.type_equivalents.items():
            if entity_type in type_tuple:
                return canonical_type
                
        return entity_type
    
    def group_entity_variants(self, entities: List[Dict]) -> List[List[Dict]]:
        """
        Group entities by their canonical names
        
        Returns:
            List of entity groups, where each group contains variants of the same entity
        """
        groups = {}
        
        for entity in entities:
            entity_name = entity.get('name', '') or entity.get('entity', '')
            if not entity_name:
                continue
                
            canonical_name = self.normalize_entity_name(entity_name)
            
            if canonical_name not in groups:
                groups[canonical_name] = []
            groups[canonical_name].append(entity)
        
        return list(groups.values())
    
    def create_merged_entity(self, entity_group: List[Dict]) -> Dict:
        """
        Create a single merged entity from a group of entity variants
        """
        if not entity_group:
            return {}
            
        # Use the first entity as base
        base_entity = entity_group[0].copy()
        
        # Merge data from all entities
        total_mentions = sum(e.get('mentions', 0) for e in entity_group)
        
        # Use canonical name
        canonical_name = self.normalize_entity_name(
            base_entity.get('name', '') or base_entity.get('entity', '')
        )
        
        # Merge types
        merged_type = self.merge_entity_types(entity_group)
        
        # Create merged entity
        merged = {
            'name': canonical_name,
            'entity': canonical_name,  # For backward compatibility
            'type': merged_type,
            'entity_type': merged_type,  # For backward compatibility
            'mentions': total_mentions,
            'variants': len(entity_group),
            'entity_ids': [e.get('id') for e in entity_group if e.get('id')],
            'power_score': base_entity.get('power_score', 0),
            'moral_score': base_entity.get('moral_score', 0),
            'national_significance': base_entity.get('national_significance'),
        }
        
        return merged


# Global instance for easy import
entity_mapper = EntityMapper()


def normalize_entity_name(name: str) -> str:
    """Convenience function for normalizing entity names"""
    return entity_mapper.normalize_entity_name(name)


def find_entity_variants(target_name: str, entity_list: List[Dict]) -> List[Dict]:
    """Convenience function for finding entity variants"""
    return entity_mapper.find_entity_variants(target_name, entity_list)


def merge_duplicate_entities(entities: List[Dict]) -> List[Dict]:
    """
    Merge duplicate entities in a list
    
    Args:
        entities: List of entity dictionaries
        
    Returns:
        List of merged entities with duplicates combined
    """
    groups = entity_mapper.group_entity_variants(entities)
    merged_entities = []
    
    for group in groups:
        if len(group) == 1:
            # No duplicates, keep as is
            merged_entities.append(group[0])
        else:
            # Merge duplicates
            merged = entity_mapper.create_merged_entity(group)
            merged_entities.append(merged)
    
    return merged_entities


if __name__ == "__main__":
    # Test the entity mapper
    test_entities = [
        {'name': 'Donald Trump', 'type': 'person', 'mentions': 880},
        {'name': 'Donald Trump', 'type': 'political_leader', 'mentions': 456},
        {'name': 'United States', 'type': 'sovereign_state', 'mentions': 700},
        {'name': 'United States', 'type': 'country', 'mentions': 402},
        {'name': 'USA', 'type': 'country', 'mentions': 100},
        {'name': 'Russia', 'type': 'country', 'mentions': 478},
    ]
    
    print("Original entities:")
    for entity in test_entities:
        print(f"  {entity['name']} ({entity['type']}): {entity['mentions']} mentions")
    
    print("\nMerged entities:")
    merged = merge_duplicate_entities(test_entities)
    for entity in merged:
        print(f"  {entity['name']} ({entity['type']}): {entity['mentions']} mentions")
        if entity.get('variants', 1) > 1:
            print(f"    (merged from {entity['variants']} variants)")