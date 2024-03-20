# Rangekeeper Grasshopper Components
This directory holds the source code for Grasshopper Components that assist the creation of Rangekeeper-compliant objects for use with Speckle.

Rangekeeper makes use of an Entity-Relationship object model to encapsulate the graph of associations between elements of a real estate asset. The walkthrough describes the intention and practicality of this in the [Loading a Design](https://daniel-fink.github.io/rangekeeper/load_design.html#object-model) notebook. 

Since there are two fundamental objects in this model, Rangekeeper provides both `Assembly` and `Entity` primitives in Grasshopper.

Consequently, there are two additional components enabling the creation of those objects:

## Create Rangekeeper Entity

![Create Rangekeeper Entity](https://github.com/daniel-fink/rangekeeper/blob/main/grasshopper/CRkE.jpg?raw=true)

Rangekeeper `Entity`s can br created from Speckle Objects. Any `name` key will be used in describing the `Entity` on the canvas. `Entity`s receive auto-generated IDs with `entityId` keys that are used when relating `Entity`s in `Assembly`s.


## Add Relationships

![Add Relationships](https://github.com/daniel-fink/rangekeeper/blob/main/grasshopper/ARkR.jpg?raw=true)

Speckle Objects and`Entity`s can be related to each other in `Assembly`s by using the `Add Relationships` component (any Speckle Objects are converted automatically to `Entity`s). Since `Assembly`s are `Entity`s, any `Entity` provided to the "Entity" input will be used as, or converted to the `Assembly`. The `Assembly` can also be used in its own source & target graph. The component matches sources & targets with relationship types sequentially (if only one relationship type is provided, it is assumed to be the same for all sources & targets)




