# Plan

- project directory: C:\brg\code_python\compas_tf

## Quarter slab

- Separate from slab.py the quarter sab geometry, where the base input is defined in floor_builder.py. Place the contents inside quarter.floor.py using the builder pattern is written in column_head.py and edge_beam.py build method. Create complex task with planning and check the memory how current classes were separated using floor_builder. After making a plan start implementing quarter slab build.

## Interfaces

- Define faces on the element fae that have a potential to create joint.
- Create a joint - columnhead - column
- Create a joint - columnhead - columnhead
- Create a joint - column - edgebeam
- Create a joint - columnhead - plate
- Create a joint - quarterslab - quarter slab
- Create a joint - quarterslab - oculusch


 