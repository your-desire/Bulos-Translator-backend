"""
Grammar Rules Engine for Bulos Language

This module provides a framework for loading, validating, and applying
grammar rules to Bulos translations. All rules must be explicitly approved
by native speakers before being used for generation.

Architecture:
- Rules are loaded from external YAML/JSON files
- Each rule has an approval status (default: NOT APPROVED)
- Unapproved rules can be used for validation only, never for generation
- Rules preserve Bulos diacritics and original vocabulary
- No assumptions about universal word order

Status: Framework Only - No Active Rules (Day 4)
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RuleStatus(Enum):
    """Approval status for grammar rules."""
    NOT_APPROVED = "not_approved"  # Default: Cannot be used for generation
    PENDING_VALIDATION = "pending_validation"  # Awaiting native speaker review
    APPROVED = "approved"  # Validated by native speakers, safe for use
    DEPRECATED = "deprecated"  # Formerly approved, no longer recommended


class RuleType(Enum):
    """Types of grammatical rules."""
    WORD_ORDER = "word_order"  # Subject-Verb-Object patterns
    MARKER = "marker"  # Grammatical particles (ay, ni, de, i, etc.)
    ADJECTIVE = "adjective"  # Adjective-noun agreement
    POSSESSION = "possession"  # Possessive constructions
    QUESTION = "question"  # Question formation
    IMPERATIVE = "imperative"  # Command/imperative constructions
    NEGATION = "negation"  # Negative constructions
    TENSE = "tense"  # Tense/aspect marking
    VALIDATION_ONLY = "validation_only"  # Can only check, not generate


@dataclass
class GrammarExample:
    """A verified example of a grammar rule."""
    bulos: str
    filipino: str
    english: str
    source_reference: str  # e.g., "sentence.json:line 42"
    notes: Optional[str] = None


@dataclass
class GrammarRule:
    """
    A single grammar rule for Bulos language.
    
    All rules default to NOT_APPROVED until explicitly validated.
    """
    rule_id: str
    rule_type: RuleType
    name: str
    description: str
    pattern: str  # Linguistic pattern description
    examples: List[GrammarExample]
    
    # Approval tracking
    status: RuleStatus = RuleStatus.NOT_APPROVED
    validated_by: Optional[str] = None  # Native speaker name
    validation_date: Optional[str] = None
    
    # Usage permissions
    allow_generation: bool = False  # Can this rule generate new translations?
    allow_validation: bool = True  # Can this rule validate existing translations?
    
    # Linguistic metadata
    required_markers: List[str] = field(default_factory=list)  # e.g., ["ay", "i"]
    word_order: Optional[str] = None  # e.g., "Adjective + i + Noun"
    substitutable_positions: List[str] = field(default_factory=list)  # Which parts can be substituted
    
    # Risk assessment
    confidence_level: str = "low"  # low, medium, high
    evidence_strength: str = "insufficient"  # insufficient, weak, moderate, strong
    known_limitations: List[str] = field(default_factory=list)
    
    # Implementation
    implementation_notes: Optional[str] = None
    
    def can_generate(self) -> bool:
        """Check if this rule can be used to generate new translations."""
        return (
            self.status == RuleStatus.APPROVED 
            and self.allow_generation 
            and self.confidence_level in ["medium", "high"]
        )
    
    def can_validate(self) -> bool:
        """Check if this rule can be used to validate translations."""
        return self.allow_validation and self.status != RuleStatus.DEPRECATED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary for serialization."""
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type.value,
            "name": self.name,
            "description": self.description,
            "pattern": self.pattern,
            "examples": [
                {
                    "bulos": ex.bulos,
                    "filipino": ex.filipino,
                    "english": ex.english,
                    "source_reference": ex.source_reference,
                    "notes": ex.notes
                }
                for ex in self.examples
            ],
            "status": self.status.value,
            "validated_by": self.validated_by,
            "validation_date": self.validation_date,
            "allow_generation": self.allow_generation,
            "allow_validation": self.allow_validation,
            "required_markers": self.required_markers,
            "word_order": self.word_order,
            "substitutable_positions": self.substitutable_positions,
            "confidence_level": self.confidence_level,
            "evidence_strength": self.evidence_strength,
            "known_limitations": self.known_limitations,
            "implementation_notes": self.implementation_notes
        }


class GrammarRulesEngine:
    """
    Engine for loading and managing Bulos grammar rules.
    
    Safety-first design:
    - All rules default to NOT_APPROVED
    - Unapproved rules cannot generate translations
    - Rules must pass validation before use
    - Preserves diacritics and original vocabulary
    """
    
    def __init__(self, rules_file: Optional[Path] = None):
        """
        Initialize the grammar rules engine.
        
        Args:
            rules_file: Path to YAML/JSON file containing grammar rules.
                       If None, initializes with empty rule set.
        """
        self.rules: Dict[str, GrammarRule] = {}
        self.rules_by_type: Dict[RuleType, List[GrammarRule]] = {
            rule_type: [] for rule_type in RuleType
        }
        
        if rules_file and rules_file.exists():
            self.load_rules(rules_file)
            logger.info(f"Grammar engine initialized with {len(self.rules)} rules from {rules_file}")
        else:
            logger.info("Grammar engine initialized with no active rules (framework only)")
    
    def load_rules(self, rules_file: Path) -> int:
        """
        Load grammar rules from YAML or JSON file.
        
        Args:
            rules_file: Path to rules file
            
        Returns:
            Number of rules loaded
            
        Raises:
            ValueError: If file format is invalid
        """
        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                if rules_file.suffix in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                elif rules_file.suffix == '.json':
                    data = json.load(f)
                else:
                    raise ValueError(f"Unsupported file format: {rules_file.suffix}")
            
            if not isinstance(data, dict) or 'rules' not in data:
                raise ValueError("Rules file must contain 'rules' key")
            
            rules_data = data['rules']
            loaded_count = 0
            
            for rule_dict in rules_data:
                try:
                    rule = self._parse_rule(rule_dict)
                    self.add_rule(rule)
                    loaded_count += 1
                except Exception as e:
                    logger.warning(f"Failed to load rule {rule_dict.get('rule_id', 'unknown')}: {e}")
            
            logger.info(f"Loaded {loaded_count}/{len(rules_data)} grammar rules")
            return loaded_count
            
        except Exception as e:
            logger.error(f"Failed to load grammar rules from {rules_file}: {e}")
            raise
    
    def _parse_rule(self, rule_dict: Dict[str, Any]) -> GrammarRule:
        """Parse a rule dictionary into a GrammarRule object."""
        # Parse examples
        examples = []
        for ex in rule_dict.get('examples', []):
            examples.append(GrammarExample(
                bulos=ex['bulos'],
                filipino=ex['filipino'],
                english=ex['english'],
                source_reference=ex['source_reference'],
                notes=ex.get('notes')
            ))
        
        # Parse rule type
        rule_type = RuleType(rule_dict['rule_type'])
        
        # Parse status
        status = RuleStatus(rule_dict.get('status', 'not_approved'))
        
        return GrammarRule(
            rule_id=rule_dict['rule_id'],
            rule_type=rule_type,
            name=rule_dict['name'],
            description=rule_dict['description'],
            pattern=rule_dict['pattern'],
            examples=examples,
            status=status,
            validated_by=rule_dict.get('validated_by'),
            validation_date=rule_dict.get('validation_date'),
            allow_generation=rule_dict.get('allow_generation', False),
            allow_validation=rule_dict.get('allow_validation', True),
            required_markers=rule_dict.get('required_markers', []),
            word_order=rule_dict.get('word_order'),
            substitutable_positions=rule_dict.get('substitutable_positions', []),
            confidence_level=rule_dict.get('confidence_level', 'low'),
            evidence_strength=rule_dict.get('evidence_strength', 'insufficient'),
            known_limitations=rule_dict.get('known_limitations', []),
            implementation_notes=rule_dict.get('implementation_notes')
        )
    
    def add_rule(self, rule: GrammarRule) -> None:
        """Add a grammar rule to the engine."""
        if rule.rule_id in self.rules:
            logger.warning(f"Rule {rule.rule_id} already exists, replacing")
        
        self.rules[rule.rule_id] = rule
        self.rules_by_type[rule.rule_type].append(rule)
        
        # Log security check
        if rule.allow_generation and rule.status != RuleStatus.APPROVED:
            logger.warning(
                f"Rule {rule.rule_id} allows generation but is not approved! "
                "This should never happen in production."
            )
    
    def get_rule(self, rule_id: str) -> Optional[GrammarRule]:
        """Get a specific rule by ID."""
        return self.rules.get(rule_id)
    
    def get_rules_by_type(self, rule_type: RuleType) -> List[GrammarRule]:
        """Get all rules of a specific type."""
        return self.rules_by_type.get(rule_type, [])
    
    def get_approved_rules(self) -> List[GrammarRule]:
        """Get all approved rules."""
        return [rule for rule in self.rules.values() if rule.status == RuleStatus.APPROVED]
    
    def get_generation_rules(self) -> List[GrammarRule]:
        """Get all rules that can be used for generation."""
        return [rule for rule in self.rules.values() if rule.can_generate()]
    
    def get_validation_rules(self) -> List[GrammarRule]:
        """Get all rules that can be used for validation."""
        return [rule for rule in self.rules.values() if rule.can_validate()]
    
    def validate_sentence(self, sentence: str, source_lang: str = "bul") -> Dict[str, Any]:
        """
        Validate a sentence against loaded grammar rules.
        
        Performs actual pattern matching against documented grammar observations.
        Only validation-enabled rules are checked (not_approved rules can validate but not generate).
        
        Args:
            sentence: Bulos sentence to validate
            source_lang: Source language code (default: "bul")
            
        Returns:
            Validation results with matched rules, confidence, and evidence
        """
        sentence_lower = sentence.lower().strip()
        words = sentence_lower.split()
        
        validation_rules = self.get_validation_rules()
        
        if not validation_rules:
            return {
                "is_valid": None,
                "matched_rules": [],
                "validation_confidence": 0.0,
                "notes": "No validation rules loaded"
            }
        
        matched_rules = []
        matched_patterns = []
        
        # Check each validation-enabled rule
        for rule in validation_rules:
            match_result = self._check_rule_match(sentence, sentence_lower, words, rule)
            
            if match_result['matches']:
                matched_rules.append(rule.rule_id)
                matched_patterns.append({
                    'rule_id': rule.rule_id,
                    'rule_name': rule.name,
                    'pattern_type': rule.rule_type.value,
                    'confidence': match_result['confidence'],
                    'evidence': match_result['evidence'],
                    'markers_found': match_result.get('markers_found', []),
                })
        
        # Calculate overall validation confidence
        if matched_rules:
            # Average confidence from all matched rules
            avg_confidence = sum(p['confidence'] for p in matched_patterns) / len(matched_patterns)
            is_valid = True
        else:
            avg_confidence = 0.0
            is_valid = False
        
        return {
            "is_valid": is_valid,
            "matched_rules": matched_rules,
            "validation_confidence": avg_confidence,
            "matched_patterns": matched_patterns,
            "notes": f"Matched {len(matched_rules)} validation rules" if matched_rules else "No pattern matches found"
        }
    
    def _check_rule_match(
        self, 
        sentence: str, 
        sentence_lower: str, 
        words: List[str], 
        rule: "GrammarRule"
    ) -> Dict[str, Any]:
        """
        Check if a sentence matches a specific grammar rule.
        
        Returns match result with confidence and evidence.
        """
        # Check by rule type
        if rule.rule_type == RuleType.MARKER and 'ay' in rule.required_markers:
            # Topic marker 'ay' construction
            if ' ay ' in sentence_lower:
                return {
                    'matches': True,
                    'confidence': 0.85,
                    'evidence': 'topic_marker_ay_found',
                    'markers_found': ['ay']
                }
        
        if rule.rule_type == RuleType.ADJECTIVE and 'i' in rule.required_markers:
            # Predicate adjective with 'i' marker
            # Pattern: [Adjective] + i + [Noun]
            if ' i ' in sentence_lower:
                # Check if there are known adjectives in the sentence
                known_adjectives = ['malawwa', 'masampat', 'hanga', 'bowon', 'malaki']
                has_adjective = any(adj in sentence_lower for adj in known_adjectives)
                
                if has_adjective:
                    return {
                        'matches': True,
                        'confidence': 0.80,
                        'evidence': 'adjective_i_marker_pattern',
                        'markers_found': ['i', 'adjective']
                    }
        
        if rule.rule_type == RuleType.POSSESSION:
            # Possessive construction with 'ni' or 'de'
            has_ni = ' ni ' in sentence_lower
            has_de = ' de ' in sentence_lower
            
            if has_ni or has_de:
                marker = 'ni' if has_ni else 'de'
                return {
                    'matches': True,
                    'confidence': 0.90,
                    'evidence': f'possessive_marker_{marker}_found',
                    'markers_found': [marker]
                }
        
        if rule.rule_type == RuleType.QUESTION:
            # Question formation with question words
            question_words = ['ànu', 'anu', 'inú', 'inu', 'dênu', 'denu', 'kapide', 'pidê', 'pide']
            
            for qword in question_words:
                if qword in sentence_lower:
                    # Check for question markers 'i' or 'ka' after question word
                    has_marker = ' i ' in sentence_lower or ' ka ' in sentence_lower
                    confidence = 0.90 if has_marker else 0.75
                    
                    return {
                        'matches': True,
                        'confidence': confidence,
                        'evidence': f'question_word_{qword}_found',
                        'markers_found': [qword]
                    }
        
        if rule.rule_type == RuleType.IMPERATIVE:
            # Imperative with inclusive pronoun 'tam'
            if ' tam ' in sentence_lower:
                return {
                    'matches': True,
                    'confidence': 0.70,
                    'evidence': 'inclusive_imperative_tam_found',
                    'markers_found': ['tam']
                }
        
        # No match found
        return {
            'matches': False,
            'confidence': 0.0,
            'evidence': 'no_pattern_match'
        }
    
    def can_generate_from_pattern(self, pattern_id: str) -> bool:
        """
        Check if a specific pattern can be used for generation.
        
        Args:
            pattern_id: Rule ID for the pattern
            
        Returns:
            True if pattern is approved for generation
        """
        rule = self.get_rule(pattern_id)
        return rule.can_generate() if rule else False
    
    def export_rules(self, output_file: Path, format: str = "yaml") -> None:
        """
        Export all rules to a file.
        
        Args:
            output_file: Path to output file
            format: 'yaml' or 'json'
        """
        data = {
            "version": "1.0",
            "engine": "Bulos Grammar Rules Engine",
            "rules": [rule.to_dict() for rule in self.rules.values()]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            if format == 'yaml':
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
            elif format == 'json':
                json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Exported {len(self.rules)} rules to {output_file}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded rules."""
        return {
            "total_rules": len(self.rules),
            "approved_rules": len(self.get_approved_rules()),
            "generation_enabled": len(self.get_generation_rules()),
            "validation_enabled": len(self.get_validation_rules()),
            "rules_by_type": {
                rule_type.value: len(rules)
                for rule_type, rules in self.rules_by_type.items()
            },
            "rules_by_status": {
                status.value: sum(1 for r in self.rules.values() if r.status == status)
                for status in RuleStatus
            }
        }


# Global instance (initialized without rules)
_grammar_engine: Optional[GrammarRulesEngine] = None


def get_grammar_engine() -> GrammarRulesEngine:
    """
    Get the global grammar engine instance.
    
    Returns:
        GrammarRulesEngine instance (initialized with no rules if not already created)
    """
    global _grammar_engine
    if _grammar_engine is None:
        _grammar_engine = GrammarRulesEngine()
    return _grammar_engine


def initialize_grammar_engine(rules_file: Optional[Path] = None) -> GrammarRulesEngine:
    """
    Initialize or reinitialize the global grammar engine.
    
    Args:
        rules_file: Optional path to rules file
        
    Returns:
        Initialized GrammarRulesEngine
    """
    global _grammar_engine
    _grammar_engine = GrammarRulesEngine(rules_file)
    return _grammar_engine
