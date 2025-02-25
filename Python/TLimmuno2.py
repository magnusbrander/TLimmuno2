import os
import pandas as pd
import numpy as np
import tensorflow as tf
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))

#load model
def model_load():
    BA_model_path = os.path.join(script_dir, "model", "BAmodel") 
    BA_model = tf.keras.models.load_model(BA_model_path)
    BAmodel = tf.keras.models.Model(inputs = BA_model.input,outputs = BA_model.layers[-2].output)
    TLimmuno2_model_path = os.path.join(script_dir, "model", "TLimmuno2") 
    TLimmuno2 = tf.keras.models.load_model(TLimmuno2_model_path)
    return BAmodel,TLimmuno2

pseudo_seq_path = os.path.join(script_dir, "data", "pseudo_blosum62.feather")
pseudo_seq = pd.read_feather(pseudo_seq_path)
pseudo_seq_file_path = os.path.join(script_dir, "data", "pseudosequence.2016.all.X.dat")
pseudo_seq_file = pd.read_table(pseudo_seq_file_path, header=None,names=("HLA","sequence"))

def blosum62(peptide,maxlen):
    Blosum62_matrix_path = os.path.join(script_dir, "data", "BLOSUM62.csv")
    Blosum62_matrix = pd.read_csv(Blosum62_matrix_path, comment="#")
    Protein_alphabet = list("ARNDCQEGHILKMFPSTWYVX")
    Blosum62_matrix = Blosum62_matrix[Protein_alphabet]
    Blosum62_matrix = Blosum62_matrix.loc[Protein_alphabet]
    encoder = np.empty((maxlen,21))
    if len(peptide) <=maxlen:
        peptide = peptide + "X"*(maxlen-len(peptide))
    for i in range(len(peptide)):
        pep = list(peptide)[i]
        coder = Blosum62_matrix[pep]
        encoder[i] = coder
    return encoder.flatten()

def data_process(args):
    mode = args.mode
    if mode == "line":
        DF = pd.DataFrame({"pep":[args.epitope],"HLA":[args.hla]})
    if mode == "file":
        DF = pd.read_csv("{}".format(args.intdir),header=None,names=("pep","HLA"))
    DF = pd.merge(DF,pseudo_seq_file)
    return DF

def peptide_code(Data):
    Data["pep_blosum"] = Data["pep"].apply(blosum62,args=(21,))
    peptide = np.empty((len(Data),21,21))
    for i in range(len(Data)):
        peptide[i] = Data["pep_blosum"][i].reshape((21,21))
    return peptide

def MHC_code(Data):
    Data["MHC_blosum"] = Data["sequence"].apply(blosum62,args=(34,))
    MHC = np.empty((len(Data),34,21))
    for i in range(len(Data)):
        MHC[i] = Data["MHC_blosum"][i].reshape((34,21))
    return MHC

def model_predict(peptide,MHC,BAmodel,TLimmuno2):
    BA = BAmodel.predict([peptide,MHC])
    IMM_result = TLimmuno2.predict([peptide,MHC,BA])
    
    return IMM_result


def rank(Data,BAmodel,TLimmuno2):
    IMM_bg_pep_path = os.path.join(script_dir, "data", "IMM_bg_pep.csv")
    IMM_bg_pep = pd.read_csv(IMM_bg_pep_path)
    IMM_bg_pep["pep_blosum"] = IMM_bg_pep["pep"].apply(blosum62,args=(21,))
    DF = pd.DataFrame()
    for i in Data.loc[:,"HLA"].unique():
        IMM_bg_pep.loc[:,"MHC"] = i
        x = pd.merge(IMM_bg_pep,pseudo_seq.loc[:,["MHC","MHC_blosum"]])
        peptide = np.empty((len(x),21,21))
        for z in range(len(x)):
            peptide[z] = x["pep_blosum"][z].reshape((21,21))
        MHC = np.empty((len(x),34,21))
        for z in range(len(x)):
            MHC[z] = x["MHC_blosum"][z].reshape((34,21))
        BA = BAmodel.predict([peptide,MHC])
        IMM_result = TLimmuno2.predict([peptide,MHC,BA])
        IMM_result = IMM_result.tolist()
        y = Data[Data["HLA"]== i]
        Rank = []
        for I in y.loc[:,"prediction"].values:
            IMM_result.append(I)
            rank = 1-(sorted(IMM_result).index(IMM_result[-1])+1)/90001
            Rank.append(rank)
            IMM_result.pop()
        y.loc[:,"Rank"] = Rank
        DF = pd.concat([DF,y])
        DF.pop("MHC_blosum")
        DF.pop("pep_blosum")
        #Todo: deal with SettingWithCopyWarning
    return DF


def main(args):
    print("Load model")
    if args.gpu != True:
        import os
        os.environ["CUDA_VISIBLE_DEVICES"]="-1" 
    BAmodel,TLimmuno2 = model_load()
    print("Data process")
    Data = data_process(args)
    peptide = peptide_code(Data)
    MHC = MHC_code(Data)
    print("Model predict")
    prediction_result = model_predict(peptide,MHC,BAmodel,TLimmuno2)
    print("Ranking (That may take a while)")
    Data["prediction"] = prediction_result
    Result = rank(Data,BAmodel,TLimmuno2)
    if args.mode == "line":
        print("epitope score : {}".format(Result["prediction"].values))
        print("epitope rank : {}".format(Result["Rank"].values))
    if args.mode == "file":
        Result.to_csv("{}/result.csv".format(args.outdir))
        print("file saved")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TLimmuno2 command line')
    parser.add_argument('--mode',type=str,default='file',help='line mode or file mode')
    parser.add_argument('--epitope',type=str,default=None,help='if line mode, specifying your epitope')
    parser.add_argument('--hla',type=str,default=None,help='if line mode, specifying your HLA allele')
    parser.add_argument('--intdir',type=str,default=None,help='if file mode, specifying the path to your input file')
    parser.add_argument('--outdir',type=str,default=None,help='if file mode, specifying the path to your output folder')
    parser.add_argument('--gpu',type=str,default=True,help='if you device don\'t have GPU, please set it to False')
    args = parser.parse_args()
    main(args)





