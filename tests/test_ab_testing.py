"""Tests for A/B testing engine"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ab_testing.ab_engine import choose_model, log_ab_result


class TestABEngine:
    """Test A/B testing engine"""
    
    def test_choose_model_deterministic(self):
        """Test that same user_id gets same model"""
        model1 = choose_model(42)
        model2 = choose_model(42)
        model3 = choose_model(42)
        
        assert model1 == model2 == model3
    
    def test_choose_model_returns_valid_version(self):
        """Test that choose_model returns valid model version"""
        for user_id in range(100):
            model = choose_model(user_id)
            assert model in ["model_A", "model_B"]
    
    def test_choose_model_distribution(self):
        """Test that models are roughly evenly distributed"""
        counts = {"model_A": 0, "model_B": 0}
        
        for user_id in range(1000):
            model = choose_model(user_id)
            counts[model] += 1
        
        # Should be roughly 50/50
        ratio = counts["model_A"] / 1000
        assert 0.4 <= ratio <= 0.6
    
    def test_log_ab_result(self, tmp_path):
        """Test logging A/B result"""
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            os.makedirs("data", exist_ok=True)
            log_ab_result(1, "model_A", "conversion")
            
            # Check file was created
            assert os.path.exists("data/ab_results.csv")
            
            with open("data/ab_results.csv", "r") as f:
                content = f.read()
                assert "1,model_A,conversion" in content
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
