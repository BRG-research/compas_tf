# compas_tf

`compas_tf` builds the timber floor as a parametric model: columns, ribs, beds,
t-sections, the oculus and the connectors that hold them together, every element
boolean-cut with its own pockets and dowel holes and checked against its
neighbours for contacts. The finished assembly is written out as JSON for
further work and as STEP for the shop.

![One bay of the timber floor](_images/banner.png)
/// caption
One bay: four quarters of ribs, beds and t-sections on a column, an oculus at
the centre, and the connectors in yellow.
///

[**The project, start to finish**](https://docs.google.com/presentation/d/1b6M9fYuQjmKMM1xWZPiqj3Y3arJCszfi/edit?slide=id.p1#slide=id.p1)
- the presentation: what is being built, why it is shaped this way, and where it
stands.

[**The latest model as STEP**](https://github.com/BRG-research/compas_tf/raw/main/data/cantilevers_baked_model.stp)
- 237 solids, 20 MB, no `compas_tf` needed to open it. The contacts are a
[second file](https://github.com/BRG-research/compas_tf/raw/main/data/cantilevers_baked_contacts.stp)
with a [JSON sidecar](https://github.com/BRG-research/compas_tf/raw/main/data/cantilevers_baked_contacts.json)
saying which two elements each contact face joins.

There are two ways into this package. **Building** the model runs the parametric
chain - guide, elements, booleans, contact search - and costs minutes.
**Reading** one opens what that chain wrote: the geometry is baked, so nothing is
recomputed and no boolean backend is involved. Most people want the second, which
is what the first four [examples](examples/010_read_model.md) do.
