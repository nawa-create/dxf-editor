
import sys
import os
import unittest
import ezdxf
from ezdxf.math import Vec3

# Add backend directory to path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.entity_linker import EntityLinker

class TestEntityLinker(unittest.TestCase):
    def setUp(self):
        self.doc = ezdxf.new()
        self.msp = self.doc.modelspace()

    def test_nearest_neighbor_assignment(self):
        """
        Test that entities are assigned to the closest text label.
        Scenario:
        - Text 'DF-01' at (0, 0)
        - Text 'DF-02' at (100, 0)
        - Line1 at (10, 0) -> Should belong to DF-01
        - Line2 at (90, 0) -> Should belong to DF-02
        - Line3 at (51, 0) -> Should belong to DF-02 (closer to 100 than 0)
        """
        # Create text entities
        part_a = self.msp.add_text("DF-01", dxfattribs={'insert': (0, 0)})
        part_b = self.msp.add_text("DF-02", dxfattribs={'insert': (100, 0)})
        
        # Create geometry entities
        line1 = self.msp.add_line((10, 0), (20, 0)) # Center approx (15, 0) -> Dist to A=15, B=85
        line2 = self.msp.add_line((90, 0), (95, 0)) # Center approx (92.5, 0) -> Dist to A=92.5, B=7.5
        line3 = self.msp.add_line((51, 0), (52, 0)) # Center approx (51.5, 0) -> Dist to A=51.5, B=48.5
        
        # Run linker
        linker = EntityLinker(self.doc)
        results = linker.link_entities()
        
        # Helper to find result by part name
        def get_linked_handles(name):
            for res in results:
                if res['part_name'] == name:
                    return res['linked_handles']
            return []

        linked_a = get_linked_handles("DF-01")
        linked_b = get_linked_handles("DF-02")
        
        # Verify
        self.assertIn(line1.dxf.handle, linked_a)
        self.assertNotIn(line2.dxf.handle, linked_a)
        
        self.assertIn(line2.dxf.handle, linked_b)
        self.assertIn(line3.dxf.handle, linked_b)

    def test_noise_filtering(self):
        """Test that entities outside search radius are ignored"""
        self.msp.add_text("DF-03", dxfattribs={'insert': (0, 0)})
        
        # Far away line
        far_line = self.msp.add_line((2000, 0), (2010, 0)) # > 1000 units away
        
        linker = EntityLinker(self.doc)
        results = linker.link_entities()
        
        # Verify DF-03 is found
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['part_name'], "DF-03")
        
        linked_c = results[0]['linked_handles']
        self.assertNotIn(far_line.dxf.handle, linked_c)

if __name__ == '__main__':
    unittest.main()
