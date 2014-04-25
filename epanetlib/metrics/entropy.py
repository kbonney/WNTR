import epanetlib.pyepanet as pyepanet
import networkx as nx
import epanetlib.network.networkx_extensions as nx_ext
import math
import numpy as np
from collections import Counter

def entropy(G):

    if G.is_directed() == False:
        return
    
    sources = [key for key,value in nx.get_node_attributes(G,'nodetype').items() if value == pyepanet.EN_RESERVOIR ]
    
    S = {}  
    Q = {}
    for nodej in G.nodes():
        sp = []
        if G.node[nodej]['nodetype']  == pyepanet.EN_JUNCTION:
            for source in sources:
                if nx.has_path(G, source, nodej):
                    simple_paths = nx_ext.all_simple_paths(G,source,target=nodej)
                    sp = sp + ([p for p in simple_paths]) 
                    # all_simple_paths was modified to check 'has_path' in the
                    # loop, but this is still slow for large networks
                    # what if the network was skeletonized based on series pipes 
                    # that have the same flow direction?
                    # what about duplicating paths that have pipes in series?
                #print j, nodeid, len(sp)
        if len(sp) == 0:
            S[nodej] = np.nan # nodej is not connected to any sources
            continue            
        
        Uj = G.predecessors(nodej) # set of nodes on the upstream ends of links incident on node j
        qij = [] # flow in link from node i to node j
        aij = []
        for nodei in Uj:
            mask = np.array([nodei in path for path in sp])
            NDij = sum(mask) # number of paths through the link from node i to node j
            if NDij == 0:
                continue  
            sp = np.array(sp)
            temp = sp[mask]
            MDij = [(t[idx],t[idx+1]) for t in temp for idx in range(len(t)-1)] # links in the NDij path
        
            flow = 0
            for link in G[nodei][nodej].keys():
                flow = flow + G[nodei][nodej][link]['weight']
            qij.append(flow)
            
            dk = Counter() # degree of link k in MDij
            for elem in MDij:
                dk[elem] += 1/len(G[elem[0]][elem[1]].keys()) # divide by the numnber of links between two nodes
            
            aij.append(NDij*(1-float(sum(np.array(dk.values()) - 1))/sum(dk.values())))
            
        Q[nodej] = sum(qij) # Total flow into node j
        
        S[nodej] = 0
        for idx in range(len(qij)):
            S[nodej] = S[nodej] - \
                qij[idx]/Q[nodej]*math.log(qij[idx]/Q[nodej]) + \
                qij[idx]/Q[nodej]*math.log(aij[idx])
                    
    Q0 = sum(nx_ext.get_edge_attributes_MG(G, 'weight').values())        

    Shat = 0
    for nodej in G.nodes():
        if not np.isnan(S[nodej]):
            if nodej not in sources:
                Shat = Shat + \
                    (Q[nodej]*S[nodej])/Q0 - \
                    Q[nodej]/Q0*math.log(Q[nodej]/Q0)
        
    return [S, Shat] 
