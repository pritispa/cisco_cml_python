class CMLPosition:
    def __init__(self, x: int, y: int) -> None:
        # x: min -5000 max 7000 - preferred
        # y: min -5000 max 5000 - preferred
        if x < -5000 or x > 7000:
            print ("Warning: Please avoid x position outside of range -5000 to 7000.")
        if y < -5000 or y > 5000:
            print ("Warning: Please avoid y position outside of range -5000 to 5000.")
        self.x = x
        self.y = y