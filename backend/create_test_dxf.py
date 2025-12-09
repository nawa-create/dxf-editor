import ezdxf
from ezdxf.enums import TextEntityAlignment
import os

def create_test_dxf():
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Define parts with vertically stacked coordinates
    parts = [
        ("DF-01", (0, 0), "Bottom Part"),   # Lowest Y
        ("DF-02", (0, 100), "Middle Part"),
        ("DF-03", (0, 200), "Top Part")     # Highest Y
    ]
    
    for name, pos, desc in parts:
        # Create a text entity for the part name
        # set_placement(pos, align) is the standard way in modern ezdxf
        msp.add_text(name, dxfattribs={'height': 10}).set_placement(pos, align=TextEntityAlignment.MIDDLE_CENTER)
        
        # Create a circle around it to represent the geometry
        msp.add_circle(pos, radius=20)
        
        print(f"Created {name} at {pos} ({desc})")

    file_path = os.path.abspath("test_spatial.dxf")
    doc.saveas(file_path)
    print(f"Saved test file to: {file_path}")

if __name__ == "__main__":
    create_test_dxf()
