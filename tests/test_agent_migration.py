import asyncio
import unittest
from unittest.mock import patch, MagicMock
from src.agents.architect import ArchitectAgent
from src.agents.sre import SREAgent

class TestAgentMigration(unittest.IsolatedAsyncioTestCase):
    async def test_architect_analyze_mock(self):
        agent = ArchitectAgent()
        agent.api_key = "dummy-key" # Force Gemini path
        
        # Mock Gemini success
        with patch('src.agents.architect.genai.Client') as mock_genai:
            mock_client = mock_genai.return_value
            mock_model = mock_client.models
            mock_response = MagicMock()
            mock_response.text = '{"updated_description": "New Design", "follow_up": "Ready", "needs_more_info": false}'
            mock_model.generate_content.return_value = mock_response
            
            result = await agent.analyze("Test Title", "Old Desc", "History")
            self.assertEqual(result["updated_description"], "New Design")
            print("✅ Meta-Testing Evidence: ArchitectAgent correctly handled Gemini response.")

    async def test_sre_diagnose_mock(self):
        agent = SREAgent()
        
        # Mock Ollama fallback
        with patch('src.agents.sre.genai.Client', side_effect=Exception("No API Key")):
            with patch('ollama.Client') as mock_ollama:
                mock_client = mock_ollama.return_value
                mock_client.chat.return_value = {
                    'message': {'content': '{"diagnosis": "Stuck Pipeline", "proposed_fix": "Restart", "action_commands": ["docker restart"], "confidence": 0.9}'}
                }
                
                result = await agent.diagnose("Pipeline Failure", "Logs here")
                self.assertEqual(result["diagnosis"], "Stuck Pipeline")
                self.assertIn("docker restart", result["action_commands"])
                print("✅ Meta-Testing Evidence: SREAgent correctly handled Ollama fallback.")

if __name__ == "__main__":
    unittest.main()
