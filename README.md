# key-value store distributed system

This was a team project of CSE138-distributed system course during fall 2023. The team members of this project were Pak Yuen Choi and Vamsi Garlapti.

# Mechanism

## Delete View Operation:

The broadcast function detects the replica being down or disconnected when writing the key-value store by broadcasting. After broadcasting, it will immediately delete the failed socket in the "VIEW" of the replica and start polling for the failed socket in another thread. When the disconnected replica reconnects, it will add the socket back to the "VIEW" and stop the polling thread. When a downed replica goes up, the downed replica will broadcast to all replicas then other replicas will make the update to the recently up replica.

## Tracking Causal metadata:

Vector clock was used to keep track of the causal metadata. The vector clock will be updated according to the number of write to a certain replica. When there is a request, it will check if the causal metadata is the same, if the input causal metadata is larger than the current causal metadata then it means it needs to handle eventual consistency. We used a hidden metadata "context" to keep track of the write history of the key-value store. This is intended for eventual consistency. Due to the implementation, the eventual consistency occurs on write, but not read. 

# To Run
Build container image and tag it:
''' $docker build -t 'tag' '''
Create a subnet with IP range 10.10.0.0/16:
''' $docker network create --subnet=10.10.0.0/16 'subnet name' '''





