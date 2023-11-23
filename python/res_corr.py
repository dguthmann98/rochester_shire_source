import uproot
#import warnings
#warnings.simplefilter(action='ignore', category=UserWarning)
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import ROOT
import os
from array import array


def get_res_correction(ntuples_gen, pull_bins, abseta_bins, nl_bins, pt_bins, pdir ,do_plot):
    #read data
    pdir = pdir+'resolution/'
    os.makedirs(pdir, exist_ok=True)
    if do_plot:
        os.makedirs(pdir+'CB_fits/', exist_ok=True)
        os.makedirs(pdir+'pol_fits/', exist_ok=True)
    ROOT.gROOT.SetBatch(1)
    ROOT.RooMsgService.instance().setGlobalKillBelow(ROOT.RooFit.ERROR)
    file=uproot.open(ntuples_gen)
    tree=file["Events"]
    variables=tree.keys()
    df=tree.arrays(variables, library="pd")

    #calculate abseta
    df["abseta_1"]=np.abs(df.eta_1)
    df["abseta_2"]=np.abs(df.eta_2)

    #calculate R
    df["R_1"]=df["genpt_1"]/df["pt_1"]
    df["R_2"]=df["genpt_2"]/df["pt_2"]


    #make histogram of distribution in abseta, nl
    if do_plot:
        plt.hist2d(df["abseta_1"],df["nTrkLayers_1"],bins=[abseta_bins, nl_bins])
        plt.colorbar()
        plt.xlabel('|eta|')
        plt.ylabel('Number of Layers')
        plt.savefig(f"./{pdir}nL_abseta.png")
        plt.savefig(f"./{pdir}nL_abseta.pdf")
        plt.clf()

        #make x axis for polynom plot later
        x_ax=np.linspace(min(pt_bins),max(pt_bins),200)

    #iterate over bins to fill histogram
    fit_par_pull=[]
    hist_std=[]
    hist_std_err=[]

    #iterate over eta bins
    for i in tqdm(range(len(abseta_bins)-1)):
        
        hist_std.append([])
        hist_std_err.append([])
        fit_par_pull.append([])

        eta_1_filter=(abseta_bins[i]<df["eta_1"]) & (df["eta_1"]<=abseta_bins[i+1])
        eta_2_filter=(abseta_bins[i]<df["eta_2"]) & (df["eta_2"]<=abseta_bins[i+1])

        df_e1=df[eta_1_filter]
        df_e2=df[eta_2_filter]

        #iterate over pt bins
        for j in range(len(nl_bins)-1):
            hist_std[i].append([])
            hist_std_err[i].append([])


            nl_1_filter=(nl_bins[j]<df_e1["nTrkLayers_1"]) & (df_e1["nTrkLayers_1"]<=nl_bins[j+1])
            nl_2_filter=(nl_bins[j]<df_e2["nTrkLayers_2"]) & (df_e2["nTrkLayers_2"]<=nl_bins[j+1])

            df_en1=df_e1[nl_1_filter]
            df_en2=df_e2[nl_2_filter]

            #calculate pull distribution
            R_1=df_en1["R_1"]
            R_2=df_en2["R_2"]
            R=pd.concat([R_1,R_2])

            std=np.std(R)
            pull=(R-np.mean(R))/std
            pull_hist=np.histogram(pull, bins=pull_bins)[0]



            # Create a ROOT TH1 object
            hist = ROOT.TH1D("hist", "PullHistogram", len(pull_bins) - 1, pull_bins)
            # Fill the histogram with data
            for k, value in enumerate(pull_hist):
                hist.SetBinContent(k+1, value)

            if hist.Integral() == 0:
                continue

            hist.Scale(1./hist.Integral())

            x = ROOT.RooRealVar("x", "m_vis (GeV)", -5, 5)
            x.setBins(10000,"cache")
            x.setMin("cache", -10)
            x.setMax("cache", 10)

            mean = ROOT.RooRealVar("mean", "mean", 0, -1, 1)
            sigma = ROOT.RooRealVar("sigma", "sigma", hist.GetStdDev(), 0, 5)
            n = ROOT.RooRealVar("n", "n", 10, 0, 1000)
            alpha = ROOT.RooRealVar("alpha", "alpha", 1, 0, 5)
            cb = ROOT.RooCrystalBall("cb", "CrystalBall", x, mean, sigma,
                                                sigma, alpha, n, alpha, n)
            roohist = ROOT.RooDataHist("roohist", "", ROOT.RooArgSet(x), hist)
            fitResult = cb.fitTo(roohist, ROOT.RooFit.AsymptoticError(True), ROOT.RooFit.PrintEvalErrors(-1))

            fit_parameters = [mean.getVal(), sigma.getVal(), n.getVal(), alpha.getVal()]
            parameter_errors = [mean.getError(), sigma.getError(), n.getError(), alpha.getError()]

            # Print the fit results
            for k, (param, error) in enumerate(zip(fit_parameters, parameter_errors)):
                print(f"Parameter {i}: {param} +/- {error}")
            
            if do_plot:
                # Create a canvas for plotting
                c1 = ROOT.TCanvas("c1", "Fitted Histogram", 800, 600)
                frame = x.frame()
                roohist.plotOn(frame, ROOT.RooFit.DrawOption("B"), ROOT.RooFit.FillStyle(0), ROOT.RooFit.FillColor(ROOT.kBlue))
                cb.plotOn(frame, ROOT.RooFit.LineColor(ROOT.kBlue))
                frame.Draw()

                # Display the canvas
                c1.Update()
                c1.Modified()

                # Optionally, save the plot as an image
                c1.SaveAs(f"./{pdir}CB_fits/eta{i}_nL{j}.png")
                    
            
            # bin in pt_reco for polynomial fit
            for k in range(len(pt_bins)-1):
                pt_1_filter=(pt_bins[k]<df_en1["pt_1"]) & (df_en1["pt_1"]<=pt_bins[k+1])
                pt_2_filter=(pt_bins[k]<df_en2["pt_2"]) & (df_en2["pt_2"]<=pt_bins[k+1])

                df_enp1=df_en1[pt_1_filter]
                df_enp2=df_en2[pt_2_filter]

                R_1=df_enp1["R_1"]
                R_2=df_enp2["R_2"]
                R=pd.concat([R_1,R_2])
                if not len(R) == 0:
                    hist_std[i][j].append(np.std(R))
                    hist_std_err[i][j].append(np.std(R)/np.sqrt(2*len(R)))
           
            hist = ROOT.TH1D("hist", "PolyHistogram", len(pt_bins) - 1, array('d', pt_bins))
            for k, value in enumerate(hist_std[i][j]):
                hist.SetBinContent(k+1, value)
                hist.SetBinError(k+1, hist_std_err[i][j][k])

            # Define the second-order polynomial function
            polynomial = ROOT.TF1("polynomial", "[0] + [1]*x + [2]*x*x")

            # Set initial parameter values
            polynomial.SetParameter(0, 0.01)  # Coefficient for the constant term
            polynomial.SetParameter(1, 5e-5)   # Coefficient for the linear term
            polynomial.SetParameter(2, 5e-5)   # Coefficient for the quadratic term

            # Fit the histogram with the plynomial function
            hist.Fit("polynomial")
            # Get the fit results
            fit_parameters = [polynomial.GetParameter(i) for i in range(3)]
            parameter_errors = [polynomial.GetParError(i) for i in range(3)]

            # Print the fit results
            for k, (param, error) in enumerate(zip(fit_parameters, parameter_errors)):
                print(f"Parameter {i}: {param} +/- {error}")
            
            if do_plot:
            # Create a canvas for plotting
                c1 = ROOT.TCanvas("c1", "Fitted Histogram", 800, 600)

                # Plot the histogram
                hist.SetMarkerStyle(ROOT.kFullCircle)
                hist.Draw("ep")

                # Plot the fitted function
                polynomial.SetLineColor(ROOT.kRed)  # Set the color to red
                polynomial.Draw("same")

                # Display the canvas
                #c1.Update()
                #c1.Modified()

                # Optionally, save the plot as an image
                c1.SaveAs(f"./{pdir}pol_fits/eta{i}_nL{j}.png")
            