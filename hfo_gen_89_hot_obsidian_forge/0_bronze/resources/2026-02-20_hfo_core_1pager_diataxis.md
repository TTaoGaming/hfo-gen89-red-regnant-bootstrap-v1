---
schema_id: hfo.gen89.diataxis.v1
medallion_layer: bronze
doc_type: explanation
title: "HFO Core 1-Pager: Stigmergy, Vectors, and the Knowledge Graph"
bluf: "A concise summary of the Hive Fractal OBSIDIAN (HFO) architecture, focusing on its three core pillars: Stigmergy (indirect coordination), Vectors (semantic understanding), and the Knowledge Graph (structured memory)."
tags: "HFO, Stigmergy, Vectors, Embeddings, Knowledge Graph, Architecture, Diataxis"
---

# HFO Core 1-Pager: Stigmergy, Vectors, and the Knowledge Graph

The **Hive Fractal OBSIDIAN (HFO)** architecture is a self-bootstrapping, multi-agent cognitive system. It operates not through direct API calls between agents, but through an environment-mediated approach. The core of this system rests on three interconnected pillars:

## 1. Stigmergy: The Indirect Coordination Trail
**"All text is stigmergy."**
Stigmergy is the mechanism of indirect coordination where the trace left in the environment by an action stimulates the performance of a next action. In HFO, agents do not talk to each other directly. Instead, they read from and write to a shared environment (the SSOT database and the file system).

*   **The Event Trail:** Every action, from a daemon heartbeat to a PREY8 session yield, is recorded as a CloudEvent in the `stigmergy_events` table.
*   **Pheromones:** Agents leave "pheromones" (metadata, tags, status flags) that other agents (like the P6 Kraken or Devourer daemons) pick up on to perform subsequent tasks (e.g., enriching a document that lacks a BLUF).
*   **Decoupling:** This allows the swarm to be highly resilient. If an agent dies, the trail remains. The next agent simply reads the trail and picks up where the last one left off.

## 2. Vectors & Embeddings: Semantic Understanding
**"Math is the universal translator."**
While stigmergy provides the *trail*, vectors provide the *meaning*. HFO uses embeddings to convert text (documents, code, events) into high-dimensional mathematical vectors.

*   **NPU Acceleration:** HFO leverages local Neural Processing Units (NPUs) to generate embeddings rapidly and efficiently without relying on cloud APIs.
*   **Semantic Search:** Instead of just keyword matching (FTS5), vectors allow agents to find conceptually related information. If an agent searches for "memory loss," the vector search can surface documents about "session state resets" or "orphaned processes."
*   **The Latent Space:** The entire SSOT is mapped into a latent space, allowing daemons to cluster similar concepts, detect anomalies, and identify gaps in the knowledge base.

## 3. The Knowledge Graph: Structured Memory
**"Depths ARE dreams. Everything that dies feeds the knowledge graph."**
The Knowledge Graph is the structured representation of all information within HFO. It is not just a collection of files, but a web of relationships.

*   **The SSOT (Single Source of Truth):** The SQLite database (`hfo_gen89_ssot.sqlite`) is the physical manifestation of the graph. It contains documents, metadata, and the stigmergy trail.
*   **Lineage & Edges:** Daemons like the P6 Kraken actively mine the SSOT to discover relationships between documents (e.g., "Doc A implements the spec in Doc B"). These relationships form the edges of the graph.
*   **Progressive Summarization:** The graph is constantly enriched. Raw data (Bronze) is summarized, tagged, and linked, eventually hardening into trusted knowledge (Gold).
*   **The Octree (8 Ports):** The graph is organized around the 8-port OBSIDIAN architecture (Observe, Bridge, Shape, Inject, Disrupt, Immunize, Assimilate, Navigate), providing a spatial and functional taxonomy for all knowledge.

## Synthesis: The PREY8 Loop
These three pillars are unified by the **PREY8 (Perceive, React, Execute, Yield)** loop. 
1.  An agent **Perceives** the environment by querying the *Knowledge Graph* and reading the *Stigmergy* trail.
2.  It **Reacts** by using *Vectors* to find relevant context and forming a plan.
3.  It **Executes** the plan, modifying the environment.
4.  It **Yields**, writing a new *Stigmergy* event and updating the *Knowledge Graph*, leaving a trail for the next cycle.