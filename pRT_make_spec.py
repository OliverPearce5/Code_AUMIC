# -*- coding: utf-8 -*-
"""
Created in Nov 2020
Edited in Jun 2022
@authors: Baptiste KLEIN, Annabella MEECH
run with python3610 (or python368) on TITAN
"""

# ----------------------------------------------------------------------------------------------------------- #
# ---------------------------------- MAKE SPEC -------------------------------------------------------------- #
# ----------------------------------------------------------------------------------------------------------- #

### Goals:
#   Generate a 1D planet atmosphere template for each order using the petitRADTRANS python module
#   https://petitradtrans.readthedocs.io/en/latest/
#   Produces model of R~10^6

### Inputs:
#   - Rp: planet radius (Rjup)
#   - Rs: stellar radius (Rsun)
#   - grav: surface gravity (cgs)
#   - Teq: planet equilibrium temp (K)
#   - Teff: stellar effective temp (K)
#   - Tint: planet interior temp (K)
#   - mmw: mean molecular weight (cgs)
#   - wmin: min wlen (um)
#   - wmax: max wlen (um)
#   - wlens-file: path to wlen file, overrules wmin/max (um)
#   - species: a list of high-res line lists to include in model


### Modules
#   - Standard python modules: numpy and time
#   - petitRADTRANS: installed on titan (on a local folder)
#     To run the code and load the module on the titan computer cluster:
#     1 - add "export PYTHONPATH=/data/atmo/petitRADTRANS-master/:$PYTHONPATH" to ~/.bashrc
#     2 - before running the code, always "source ~/.bashrc"
#     3 - Run code: "python368 make_spec.py"

#     Before using the code --> Create a repository called 'Model' to store the planet atmosphere template generated
#     WARNING: The planet atmosphere template are not normalized

#     Adjust abundances below

# ----------------------------------------------------------------------------------------------------------- #

import argparse
import numpy as np
import os
import time
from petitRADTRANS import Radtrans
from petitRADTRANS import nat_cst as nc
import pickle

def compute_model(wmin,wmax,wfactor):
    lamb_inf,lamb_sup = (1-wfactor)*wmin,wmax*(1+wfactor)

    ### make model
    atmosphere = Radtrans(line_species = LS, \
                      rayleigh_species = ['H2', 'He'], \
                      continuum_opacities = ['H2-H2', 'H2-He'], \
                      wlen_bords_micron = [lamb_inf,lamb_sup], \
                      mode = 'lbl', \
                      lbl_opacity_sampling=10)

    atmosphere.setup_opa_structure(pressures)

    atmosphere.calc_transm(temperature,abundances,gravity,MMW,\
                               R_pl=Rp,P0_bar=P0)

    ### Get the corresponding relative variation of flux (DF)
    Rtransit = atmosphere.transm_rad
    wlens   = nc.c/atmosphere.freq #cm
    wlens /= 1e-4

    return Rtransit, wlens


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("planet", help='planet name')
    parser.add_argument("--Rp", type=float, required=True, help='planet radius (Rjup)')
    parser.add_argument("--Rs", type=float, required=True, help='stellar radius (Rsun)')
    parser.add_argument("--grav", type=float, required=True, help='surface gravity (cgs)')
    parser.add_argument("--Teq", type=int, required=True, help='planet equilibrium temp (K)')
    parser.add_argument("--Teff", type=int, default=None, help='stellar effective temp (K)')
    parser.add_argument("--Tint", type=int, default=None, help='planet interior temp (K)')
    parser.add_argument("--mmw", type=float, required=True, help='mean molecular weight (cgs)')
    parser.add_argument("--wmin", type=float, default=1.2, help='min wlen (um), use for a single model')
    parser.add_argument("--wmax", type=float, default=2.5, help='max wlen (um), use for a single model')
    parser.add_argument("--wlens-file", type=str, default=None, \
        help='path to wlen file, overrules wmin/max (um), can use for order_by_order models')
    parser.add_argument("--species", type=str, default=['H2'], nargs='+', \
        help='lbl species, see https://petitradtrans.readthedocs.io/en/latest/content/available_opacities.html for full list')



    args = parser.parse_args()

    # Create directory for models
    #save_dir = '{:s}_pRTmodels/'.format(args.planet)
    save_dir = 'pRT_models/'
    if not os.path.exists(save_dir): os.makedirs(save_dir)

    # ----------------------------------------------------------------------------------------------------------- #
    ####### PLANET PARAMETERS -- USER INPUT
    # ----------------------------------------------------------------------------------------------------------- #

    Rp        = args.Rp*nc.r_jup_mean     # Planet radius [cm]
    Rs        = args.Rs*nc.r_sun          # Stellar radius [cm]
    gravity   = args.grav                 # Planet surface gravity [cgs]
    P0        = 0.01                      # Reference pressure [bar]
    Teq       = args.Teq                  # Planet equilibrium temperature [K] -- Isothermal model
    mmw       = args.mmw                  # Mean molecular weight [cgs]
    wfactor   = 0.01                   # Multiplicative factor to extend the wavelength ranges for petitRADTRANS
                                          # e.g., wfactor = 0.01 means that the wavelength range is 1% larger than the  min/max wavelengths in the input wave file

    Teff      = args.Teff
    Tint      = args.Tint

    pressures = np.logspace(-10, 2, 100)  # Pressure grid [bar]
    if Teff is not None:
        temperature = Teff*(Tint^4+Teq^4)**0.25 * np.ones_like(pressures)
    else:
        temperature  = Teq * np.ones_like(pressures)
    MMW       = mmw * np.ones_like(temperature)

    ### lbl species  --  for petitRADTRANS
    #LS = ['H2O_main_iso','CO_all_iso','NH3_main_iso','CO2_main_iso','CH4_main_iso','HCN_main_iso']
    species   = args.species
    LS        = []
    if 'CO' in species: LS.append('CO_all_iso')
    if 'H2O' in species: LS.append('H2O_main_iso')
    if 'CO2' in species: LS.append('CO2_main_iso')
    if 'CH4' in species: LS.append('CH4_main_iso')
    if 'HCN' in species: LS.append('HCN_main_iso')
    if 'NH3' in species: LS.append('NH3_main_iso')
    if 'H2' in species: LS.append('H2_main_iso')
    print("\nIncluding species: {}".format(LS))

    t0 = time.time()
    print("\nInitialise model")

    ### Abundances in MASSIVE FRACTIONS - set to solar
    solar = '1x'
    abundances                   =  {}
    abundances['H2']             =  0.71 * np.ones_like(pressures)
    abundances['He']             =  0.27 * np.ones_like(pressures)
    abundances['H2O_main_iso']            =  1e-3 * np.ones_like(pressures)
    abundances['CO_all_iso']     =  1e-3 * np.ones_like(pressures)
    abundances['NH3']            =  2.2e-5* np.ones_like(pressures)
    abundances['CO2_main_iso']            =  1e-4 * np.ones_like(pressures)
    abundances['CH4_main_iso']            =  1e-3 * np.ones_like(pressures)
    abundances['HCN_main_iso']            =  1.1e-4* np.ones_like(pressures)

    #abundances['CO_all_iso']     = 0.012* np.ones_like(pressures)
    #abundances['NH3_main_iso']   = 2.2 * 10**(-5) * np.ones_like(pressures)
    #abundances['CO2_main_iso']   = 1.0 * 10**(-5) * np.ones_like(pressures)
    #abundances['CH4_main_iso']   = 3.4*10**(-4) * np.ones_like(pressures)
    #abundances['HCN_main_iso']   = 1.1*10**(-4)* np.ones_like(pressures)


    # ----------------------------------------------------------------------------------------------------------- #
    ####### WAVELENGTHS - in microns
    # ----------------------------------------------------------------------------------------------------------- #
    if args.wlens_file is not None:
        rep_wave   = args.wlens_file   ## Name of the input file listing the order nb, min/max/mean wavelengths for each order
        order_by_order = True
        #A          = np.loadtxt(rep_wave,skiprows=1) # assuming these are table, including wlens FOR EACH ORDER
        #det        = np.array(A[:,0],dtype=int)
        #ndet       = len(det)
        #W_min      = A[:,1]
        #W_max      = A[:,2]
        #Wm         = A[:,3]
        A          = pickle.load(open(rep_wave,'rb'))
        ndet       = len(A)
        W_min      = []
        W_max      = []
        for idet in range(ndet):
            W_min.append(A[idet][0])
            W_max.append(A[idet][-1])
        W_min      = np.array(W_min)
        W_max      = np.array(W_max)
        W_min /= 1e3 #convert to um
        W_max /= 1e3
        Wm         = (W_min+W_max)/2 # not needed?
        det        = np.arange(ndet) # at some point edit this to correspond to actual order numbers

    else:
        order_by_order = False
        W_min = args.wmin
        W_max = args.wmax
        Wm = (W_min+W_max)/2
        ndet = 1
        det = [1]


    # specfic directory for these models
    sp = '_'.join(i for i in species)
    save_dir += '{:s}_{}Solar_{}_R1M/'.format(args.planet,solar,sp)
    if order_by_order:
        print('\ncomputing a single model for each order')
        save_dir += 'order_by_order/'
    if not os.path.exists(save_dir): os.makedirs(save_dir)
    # ----------------------------------------------------------------------------------------------------------- #
    ####### MAIN LOOP - COMPUTE MODEL FOR EACH ORDER
    # ----------------------------------------------------------------------------------------------------------- #
    for idet in range(ndet):
        tx = "Order " + str(det[idet])
        print(tx)
        Rtransit,wlens = compute_model(W_min,W_max,wfactor)

        DF   = -1.0* Rtransit**(2)/Rs**(2)
        ### Store the results
        #rep_fin = save_dir+ 'template_' + str(det[idet]) + '.bin'
        rep_fin = save_dir+ 'template_det' +str(det[idet]) + '.pic'

        #file = open(rep_fin,'w')
        #tx   = '### Model atmosphere {} - Order {} \n'.format(args.planet,det[idet])
        #tx  += '### Code: petitRADTRANS - 1D homogeneous isothermal atmosphere\n'
        #tx  += '### Massive fractions: '

        #for key in abundances:
        #    tx += str(key) + ": " + str(abundances[key][0]) + " "
        #tx += "\n"

        #tx  += '### T_eq = ' + str(Teq) +  ' K - mu = ' + str(mmw) + '\n'
        #tx  += '### Wavelength  -Rp^2/Rs^2\n'
        #file.write(tx)
        #for nn in range(len(DF)):
        #    tx = str(wlens[nn]) + ' ' + str(DF[nn]) + '\n'
        #    file.write(tx)
        #file.close()

        pickle.dump([wlens,DF],open(rep_fin,'wb'),protocol=2)
        # lines 148-165 would be good to save as pickles instead (the full spectral matrices and wavelengths in one file) - much more efficient

    t1  = time.time()
    tx  = "DONE\n"
    tx += "Total duration: " + str((t1-t0)/60.0) + " min"
    print(tx)
