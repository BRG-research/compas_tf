# Read the Breps

The STEP file is the same geometry with no compas_tf concepts in it: no
elements, no tree, no features. Solids, the way a shop gets them.

![The same building read back from STEP](../_images/example_model_20_read_brep.png)
/// caption
The model as STEP - 237 solids, 19.5 MB, no compas_tf needed to open it. The
same building as the page before, and the same picture, but compare the scene
tree: two flat entries, `model` and `contacts`. STEP carries no names and no
hierarchy, so there is nothing to mirror. The 3.9 MB JSON keeps all three - the
names, the tree and the contacts.
///

```python
--8<-- "examples/example_model_20_read_brep.py"
```

```text
237 solids, 4779 faces, 733 contacts
```

The model is written as one compound, so `.solids` splits out the parts. The
contacts are a second file, because they are loose planar faces and `.solids`
would drop them.

Each solid had its coplanar faces merged before it was written, so a face the
boolean left as triangle soup is one flat face again and a drilled face is ONE
face carrying its hole loops. That is 13730 mesh faces against 4779 Brep faces.

Two things to know:

**Set the deflection.** COMPAS defaults `TOL.lineardeflection` to `0.001`, a
1 micron chord tolerance on a building. The twisted loft quads then tessellate
to 2.93M triangles in 67 s; at `1.0` it is 19.8k triangles in 2.0 s for the same
picture.

**STEP drops per-shape names.** Every face reads back unnamed, so this page can
draw the contacts but cannot say which two elements any of them joins. It does
preserve their *order*, and the `cantilevers_baked_contacts.json` sidecar
written alongside describes face *i* in record *i* - see
[Read the Breps with their adjacency](025_read_brep_adjacency.md).
