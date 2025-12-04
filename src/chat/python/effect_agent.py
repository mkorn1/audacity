#!/usr/bin/env python3
"""
Effect Agent
Handles effect application tasks:
- Effect selection and validation
- Parameter handling
- Effect application workflow
"""

from typing import Dict, Any, Optional
from tools import ToolExecutor, EffectTools


class EffectAgent:
    """
    Specialized agent for effect operations
    """
    
    def __init__(self, tools: EffectTools):
        """
        Initialize effect agent
        
        Args:
            tools: EffectTools instance
        """
        self.tools = tools
        self.available_effects = [
            "NoiseReduction",
            "Amplify",
            "Normalize",
            "FadeIn",
            "FadeOut",
            "Compressor",
            "Limiter",
            "Reverb",
            "Invert",
            "Reverse"
        ]
    
    def handle_task(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an effect task
        
        Args:
            action: Action to perform (e.g., "apply", "open")
            parameters: Action parameters, must include "effect" for apply/open
            
        Returns:
            Dict with result
        """
        if action == "apply":
            return self._apply_effect(parameters)
        elif action == "open":
            return self._open_effect(parameters)
        else:
            return {
                "success": False,
                "error": f"Unknown effect action: {action}"
            }
    
    def _apply_effect(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply an effect
        
        Args:
            parameters: Must contain "effect" (effect name/ID)
        """
        effect_name = parameters.get("effect")
        if not effect_name:
            return {
                "success": False,
                "error": "Effect name not provided"
            }
        
        # Validate effect
        if not self._validate_effect(effect_name):
            return {
                "success": False,
                "error": f"Unknown or invalid effect: {effect_name}"
            }
        
        # Map common names to effect IDs
        effect_id = self._map_effect_name_to_id(effect_name)
        
        # Open effect dialog (user will configure and apply)
        result = self.tools.open_effect(effect_id)
        
        # Note: In Phase 3, we'll add approval workflow here
        # For now, just open the dialog
        
        return {
            "success": result.get("success", False),
            "effect": effect_id,
            "message": f"Effect dialog opened for {effect_id}"
        }
    
    def _open_effect(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Open effect dialog without applying"""
        return self._apply_effect(parameters)
    
    def _validate_effect(self, effect_name: str) -> bool:
        """
        Validate that effect name/ID is available
        """
        effect_id = self._map_effect_name_to_id(effect_name)
        return effect_id in self.available_effects
    
    def _map_effect_name_to_id(self, effect_name: str) -> str:
        """
        Map human-readable effect name to effect ID
        """
        name_lower = effect_name.lower()
        
        # Direct match
        if effect_name in self.available_effects:
            return effect_name
        
        # Name mappings
        mappings = {
            "noise reduction": "NoiseReduction",
            "noise": "NoiseReduction",
            "remove noise": "NoiseReduction",
            "amplify": "Amplify",
            "volume": "Amplify",
            "gain": "Amplify",
            "normalize": "Normalize",
            "fade in": "FadeIn",
            "fadein": "FadeIn",
            "fade out": "FadeOut",
            "fadeout": "FadeOut",
            "compressor": "Compressor",
            "compress": "Compressor",
            "limiter": "Limiter",
            "limit": "Limiter",
            "reverb": "Reverb",
            "invert": "Invert",
            "reverse": "Reverse"
        }
        
        return mappings.get(name_lower, effect_name)
    
    def get_effect_parameters(self, effect_id: str) -> Dict[str, Any]:
        """
        Get default parameters for an effect
        Note: This would query the effect system
        For now, returns placeholder
        """
        # TODO: Implement with state reader or effect system query
        return {}
    
    def validate_effect_parameters(self, effect_id: str, parameters: Dict[str, Any]) -> bool:
        """
        Validate effect parameters
        Note: This would validate against effect schema
        For now, returns True
        """
        # TODO: Implement parameter validation
        return True

