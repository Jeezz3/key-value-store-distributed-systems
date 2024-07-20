# CSE138_Assignment3

Team Contributions: Pak Yuen Choi: Worked on the view operations and the key-value operations of the project and tested the code. Vamsi Garlapati: Helped plan the code for the view operations and key-value operations of the project, helped with coding the view operations and the key-value operations of the project, tested the code, and worked on the README file.

Acknowledgments: N/A

Citations: Flask Documentation

# Mechanism

## Delete View Operation:

The broadcast function detects the replica being down or disconnected when writing the key-value store. The broadcast function discovered that a certain replica was down or disconnected during broadcasting. After broadcasting, it will immediately delete the failed socket in the "VIEW" of the replica and start polling for the failed socket in another thread. 

When the disconnected replica reconnects, it will add the socket back to the "VIEW" and stop the polling thread

When a replica goes down and then goes up, the downed replica will broadcast to all replicas. Then other replicas will make the update the downed replica.

## Tracking Causal metadata:

We used a vector clock to keep track of the causal metadata. The vector clock will be updated according to the number of write to a certain replica. When there is a request it will check if the causal metadata is the same, if the input causal metadata is larger than the current causal metadata then it means it needs to handle eventual consistency. We used a hidden metadata "context" to keep track of the write history of the key-value store. This is intended for eventual consistency. Due to the implementation, the eventual consistency occurs on write, but not read. 




