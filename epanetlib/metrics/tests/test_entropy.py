from nose.tools import *
from os.path import abspath, dirname, join
import numpy as np

import sys
sys.path.append('C:\kaklise\EPA-Resilience\Evaluation Tool')
import epanetlib as en

testdir = dirname(abspath(str(__file__)))
datadir = join(testdir,'..','..','..','networks')

def test_layout1():
    enData = en.pyepanet.ENepanet()
    enData.inpfile = join(datadir,'Awumah_layout1.inp') 
    enData.ENopen(enData.inpfile,'tmp.rpt')
    
    attr = {('1', '2', '1'): 940.7,
            ('2', '3', '2'): 550.0,
            ('1', '4', '3'): 659.3,
            ('2', '5', '4'): 290.7,
            ('3', '6', '5'): 400.0,
            ('4', '5', '6'): 59.3,
            ('4', '7', '7'): 450.0, 
            ('5', '8', '8'): 200.0, 
            ('6', '9', '9'): 300.0, 
            ('7', '10', '10'): 250.0,
            ('9', '12', '11'): 100.0,
            ('10', '11', '12'): 150.0}
            
    G = en.network.epanet_to_MultiDiGraph(enData, edge_attribute=attr)
    en.network.draw_graph(G, edge_attribute='weight') 
    
    [S, Shat] = en.metrics.entropy(G)
    
    expected_Saverage = 0.088
    error = abs((np.mean(S.values()) - expected_Saverage)/expected_Saverage)
    assert_less(error, 0.05) # 5% error
    
    expected_Smax = 0.5130
    error = abs((max(S.values()) - expected_Smax)/expected_Smax)
    assert_less(error, 0.05) # 5% error
    
    expected_Shat = 2.280
    error = abs((Shat - expected_Shat)/expected_Shat)
    assert_less(error, 0.05) # 5% error


def test_layout8():
    enData = en.pyepanet.ENepanet()
    enData.inpfile = join(datadir,'Awumah_layout8.inp') 
    enData.ENopen(enData.inpfile,'tmp.rpt')
    
    attr = {('1', '2', '1'): 678.8,
            ('2', '3', '2'): 403.3,
            ('1', '4', '3'): 921.2,
            ('2', '5', '4'): 175.5,
            ('3', '6', '5'): 253.3,
            ('4', '5', '6'): 227.1,
            ('5', '6', '7'): 126.3,
            ('4', '7', '8'): 544.1, 
            ('5', '8', '9'): 126.3, 
            ('6', '9', '10'): 279.6, 
            ('7', '8', '11'): 200.0,
            ('7', '10', '12'): 144.1,
            ('8', '11', '13'): 126.3,
            ('9', '12', '14'): 79.6,
            ('10', '11', '15'): 44.1,
            ('11', '12', '16'): 20.4}
            
    G = en.network.epanet_to_MultiDiGraph(enData, edge_attribute=attr)
    en.network.draw_graph(G, edge_attribute='weight') 
    
    [S, Shat] = en.metrics.entropy(G)
    
    expected_Saverage = 0.3860
    error = abs((np.mean(S.values()) - expected_Saverage)/expected_Saverage)
    assert_less(error, 0.05) # 5% error
    
    expected_Smax = 0.5130
    error = abs((max(S.values()) - expected_Smax)/expected_Smax)
    assert_less(error, 0.05) # 5% error
    
    expected_Shat = 2.670
    error = abs((Shat - expected_Shat)/expected_Shat)
    assert_less(error, 0.05) # 5% error
    
if __name__ == '__main__':
    test_layout8()