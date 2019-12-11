# -*- coding: utf-8 -*-
"""
Created on Wed Sep 19 09:41:27 2018

@author: Thanh Tung Khuat

Simple combination of online learning and agglomerative learning gfmm

Doing online learning first by using small values of maximum hyperbox size, then perform agglomerative learning with V and W sets generated by the online learning process
            
        OnlineAggloGFMM(gamma, teta_onl, teta_agglo, bthres, simil, sing, isDraw, oper, isNorm, norm_range, V_pre, W_pre, classId_pre)

    INPUT
        gamma           Membership function slope (default: 1)
        teta_onl        Maximum hyperbox size (default: 1) for online learning
        teta_agglo      Maximum hyperbox size (default: 1) for agglomerative v2 learning
        bthres          Similarity threshold for hyperbox concatenation (default: 0.5)
        simil           Similarity measure: 'short', 'long' or 'mid' (default: 'mid')
        sing            Use 'min' or 'max' (default) memberhsip in case of assymetric similarity measure (simil='mid')
        isDraw          Progress plot flag (default: False)
        oper            Membership calculation operation: 'min' or 'prod' (default: 'min')
        isNorm          Do normalization of input training samples or not?
        norm_range      New ranging of input data after normalization, for example: [0, 1]
        V_pre           Hyperbox lower bounds for the model to be updated using new data
        W_pre           Hyperbox upper bounds for the model to be updated using new data
        classId_pre     Hyperbox class labels (crisp)  for the model to be updated using new data   
  
    ATTRIBUTES:
        V               Hyperbox lower bounds
        W               Hyperbox upper bounds
        classId         Hyperbox class labels (crisp)
        cardin          Hyperbox cardinalities (the number of training samples is covered by corresponding hyperboxes)
        clusters        Identifiers of input objects in each hyperbox (indexes of training samples covered by corresponding hyperboxes)

"""

import sys, os
sys.path.insert(0, os.path.pardir)

import ast
import time
import numpy as np
import matplotlib
try:
    matplotlib.use('TkAgg')
except:
    pass

from functionhelper.preprocessinghelper import loadDataset, string_to_boolean
from GFMM.basebatchlearninggfmm import BaseBatchLearningGFMM
from GFMM.faster_onlinegfmm import OnlineGFMM
from GFMM.faster_accelbatchgfmm import AccelBatchGFMM
from GFMM.batchgfmm import BatchGFMMV1
from GFMM.classification import predict_with_probability, predict

class OnlineAggloGFMM(BaseBatchLearningGFMM):
    
    def __init__(self, gamma = 1, teta_onl = 1, teta_agglo = 1, bthres = 0.5, simil = 'mid', sing = 'max', isDraw = False, oper = 'min', isNorm = True, norm_range = [0, 1], V_pre = np.array([], dtype=np.float64), W_pre = np.array([], dtype=np.float64), classId_pre = np.array([], dtype=np.int16)):
        BaseBatchLearningGFMM.__init__(self, gamma, teta_onl, isDraw, oper, isNorm, norm_range)
        
        self.teta_onl = teta_onl
        self.teta_agglo = teta_agglo
        
        self.V = V_pre
        self.W = W_pre
        self.classId = classId_pre
        
        self.bthres = bthres
        self.simil = simil
        self.sing = sing
        
    
    def fit(self, X_l, X_u, patClassId, typeOfAgglo = 1):
        """
        Xl              Input data lower bounds (rows = objects, columns = features)
        Xu              Input data upper bounds (rows = objects, columns = features)
        patClassId      Input data class labels (crisp)
        typeOfAgglo     Type of agglomerative learning
                         + 1: Accelerated agglomerative learning AGGLO-2
                         + 2: Full batch learning slower version
                         + 3: Full batch learning faster version
        """
        if self.isNorm == True:
            X_l, X_u = self.dataPreprocessing(X_l, X_u)
            
        time_start = time.clock()
        # Perform online learning
        onlClassifier = OnlineGFMM(self.gamma, self.teta_onl, self.teta_onl, isDraw = self.isDraw, oper = self.oper, isNorm = False, norm_range = [self.loLim, self.hiLim], V = self.V, W = self.W, classId = self.classId)
        # training for online GFMM
        onlClassifier.fit(X_l, X_u, patClassId)
        
        self.V = onlClassifier.V
        self.W = onlClassifier.W
        self.classId = onlClassifier.classId
        # print('No. hyperboxes after online learning:', len(self.classId))
        self.num_hyperbox_after_online = len(self.classId)
        
        # Perform agglomerative learning
        if typeOfAgglo == 1:
            aggloClassifier = AccelBatchGFMM(self.gamma, self.teta_agglo, bthres = self.bthres, simil = self.simil, sing = self.sing, isDraw = self.isDraw, oper = self.oper, isNorm = False)
        elif typeOfAgglo == 2:
            aggloClassifier = BatchGFMMV2(self.gamma, self.teta_agglo, bthres = self.bthres, simil = self.simil, sing = self.sing, isDraw = self.isDraw, oper = self.oper, isNorm = False)
        else:
            aggloClassifier = BatchGFMMV1(self.gamma, self.teta_agglo, bthres = self.bthres, simil = self.simil, sing = self.sing, isDraw = self.isDraw, oper = self.oper, isNorm = False)
            
        aggloClassifier.fit(self.V, self.W, self.classId)
        
        self.V = aggloClassifier.V
        self.W = aggloClassifier.W
        self.classId = aggloClassifier.classId
        self.cardin = aggloClassifier.cardin
        #print('No. hyperboxes after the agglomerative learning:', len(self.classId))
        self.num_hyperbox_after_agglo = len(self.classId)
        
        time_end = time.clock()
        self.elapsed_training_time = time_end - time_start
        
        return self
    
    def predict(self, Xl_Test, Xu_Test, patClassIdTest, newVer = True):
        """
        Perform classification

            result = predict(Xl_Test, Xu_Test, patClassIdTest)

        INPUT:
            Xl_Test             Test data lower bounds (rows = objects, columns = features)
            Xu_Test             Test data upper bounds (rows = objects, columns = features)
            patClassIdTest	    Test data class labels (crisp)
            newVer              + True: Using cardinality to support the classification process
                                + False: No use of an additional criterion

        OUTPUT:
            result        A object with Bunch datatype containing all results as follows:
                          + summis           Number of misclassified objects
                          + misclass         Binary error map
                          + sumamb           Number of objects with maximum membership in more than one class
                          + out              Soft class memberships
                          + mem              Hyperbox memberships
        """
        #Xl_Test, Xu_Test = delete_const_dims(Xl_Test, Xu_Test)
        # Normalize testing dataset if training datasets were normalized
        if len(self.mins) > 0:
            noSamples = Xl_Test.shape[0]
            Xl_Test = self.loLim + (self.hiLim - self.loLim) * (Xl_Test - np.ones((noSamples, 1)) * self.mins) / (np.ones((noSamples, 1)) * (self.maxs - self.mins))
            Xu_Test = self.loLim + (self.hiLim - self.loLim) * (Xu_Test - np.ones((noSamples, 1)) * self.mins) / (np.ones((noSamples, 1)) * (self.maxs - self.mins))

            if Xl_Test.min() < self.loLim or Xu_Test.min() < self.loLim or Xl_Test.max() > self.hiLim or Xu_Test.max() > self.hiLim:
                print('Test sample falls outside', self.loLim, '-', self.hiLim, 'interval')
                print('Number of original samples = ', noSamples)

                # only keep samples within the interval loLim-hiLim
                indXl_good = np.where((Xl_Test >= self.loLim).all(axis = 1) & (Xl_Test <= self.hiLim).all(axis = 1))[0]
                indXu_good = np.where((Xu_Test >= self.loLim).all(axis = 1) & (Xu_Test <= self.hiLim).all(axis = 1))[0]
                indKeep = np.intersect1d(indXl_good, indXu_good)

                Xl_Test = Xl_Test[indKeep, :]
                Xu_Test = Xu_Test[indKeep, :]

                print('Number of kept samples =', Xl_Test.shape[0])
                #return

        # do classification
        result = None

        if Xl_Test.shape[0] > 0:
            if newVer:
                result = predict_with_probability(self.V, self.W, self.classId, self.cardin, Xl_Test, Xu_Test, patClassIdTest, self.gamma)
            else:
                result = predict(self.V, self.W, self.classId, Xl_Test, Xu_Test, patClassIdTest, self.gamma)
                
            self.predicted_class = np.array(result.predicted_class, np.int)

        return result
    

if __name__ == '__main__':
    """
    INPUT parameters from command line
    
    arg1:  + 1 - training and testing datasets are located in separated files
           + 2 - training and testing datasets are located in the same files
    arg2:  path to file containing the training dataset (arg1 = 1) or both training and testing datasets (arg1 = 2)
    arg3:  + path to file containing the testing dataset (arg1 = 1)
           + percentage of the training dataset in the input file
    arg4:  + True: drawing hyperboxes during the training process
           + False: no drawing
    arg5:  + Maximum size of hyperboxes of online learning algorithm (teta_onl, default: 1)
    arg6:  + Maximum size of hyperboxes of agglomerative learning algorithm (teta_agglo, default: 1)
    arg7:  + gamma value (default: 1)
    arg8:  + Similarity threshod (default: 0.5)
    arg9:  + Similarity measure: 'short', 'long' or 'mid' (default: 'mid')
    arg10: + operation used to compute membership value: 'min' or 'prod' (default: 'min')
    arg11: + do normalization of datasets or not? True: Normilize, False: No normalize (default: True)
    arg12: + range of input values after normalization (default: [0, 1])   
    arg13: + Use 'min' or 'max' (default) memberhsip in case of assymetric similarity measure (simil='mid')
    arg14: + Type of agglomerative learning
                - 1: Accelerated agglomerative learning AGGLO-2
                - 2: Full batch learning slower version
                - 3: Full batch learning faster version
    """
    
    # Init default parameters
    if len(sys.argv) < 5:
        isDraw = False
    else:
        isDraw = string_to_boolean(sys.argv[4])
    
    if len(sys.argv) < 6:
        teta_onl = 1    
    else:
        teta_onl = float(sys.argv[5])
    
    if len(sys.argv) < 7:
        teta_agglo = 1
    else:
        teta_agglo = float(sys.argv[6])
    
    if len(sys.argv) < 8:
        gamma = 1
    else:
        gamma = float(sys.argv[7])
    
    if len(sys.argv) < 9:
        bthres = 0.5
    else:
        bthres = float(sys.argv[8])
    
    if len(sys.argv) < 10:
        simil = 'mid'
    else:
        simil = sys.argv[9]
    
    if len(sys.argv) < 11:
        oper = 'min'
    else:
        oper = sys.argv[10]
    
    if len(sys.argv) < 12:
        isNorm = True
    else:
        isNorm = string_to_boolean(sys.argv[11])
    
    if len(sys.argv) < 13:
        norm_range = [0, 1]
    else:
        norm_range = ast.literal_eval(sys.argv[12])
        
    if len(sys.argv) < 14:
        sing = 'max'
    else:
        sing = sys.argv[13]
        
    if len(sys.argv) < 15:
        typeOfAgglo = 1
    else:
        typeOfAgglo = int(sys.argv[14])
        
    if sys.argv[1] == '1':
        training_file = sys.argv[2]
        testing_file = sys.argv[3]

        # Read training file
        Xtr, X_tmp, patClassIdTr, pat_tmp = loadDataset(training_file, 1, False)
        # Read testing file
        X_tmp, Xtest, pat_tmp, patClassIdTest = loadDataset(testing_file, 0, False)
    
    else:
        dataset_file = sys.argv[2]
        percent_Training = float(sys.argv[3])
        Xtr, Xtest, patClassIdTr, patClassIdTest = loadDataset(dataset_file, percent_Training, False)
    
    
    classifier = OnlineAggloGFMM(gamma, teta_onl, teta_agglo, bthres, simil, sing, isDraw, oper, isNorm, norm_range)
    classifier.fit(Xtr, Xtr, patClassIdTr, typeOfAgglo)
    
    # Testing
    print("-- Testing --")
    result = classifier.predict(Xtest, Xtest, patClassIdTest)
    if result != None:
        print("Number of wrong predicted samples = ", result.summis)
        numTestSample = Xtest.shape[0]
        print("Error Rate = ", np.round(result.summis / numTestSample * 100, 2), "%")
   