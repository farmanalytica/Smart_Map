# -*- coding: utf-8 -*-
"""
/***************************************************************************
# File: semivariogram.py

                                 A QGIS plugin

                              -------------------
        begin                : 2018-08-15
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Gustavo Willam Pereira
                                           Domingos Sárvio Magalhães Valente 
                                           Daniel Marçal de Queiroz
                                           Andre Luiz de Freitas Coelho
                                           Sandro Manuel Carmelino Hurtado
        email                : gustavowillam@gmail.com
 ***************************************************************************/
"""

import os 
import numpy as np
from scipy.optimize import curve_fit
import pandas as pd
import itertools as it
from scipy import spatial
from . import variogram_models
import platform


file_dir = os.path.dirname(os.path.abspath(__file__))                          # directory of this Python file
name_log = 'log.txt'


def Log(msg):
    
    f = open(os.path.join(file_dir, name_log), "a")
    f.write(msg+'\n')
    f.close()


system = platform.system()  #[Windows, Linux, Darwin]

   
if system != 'Darwin':  # macOS errors when writing the semivariogram log to a txt file    

    
    f = open(os.path.join(file_dir, name_log), 'w')                                #open(name_log, "w")
    f.write('\nSmartMap Log File\n')
    f.close()


class Semivariogram:

    # Theoretical semivariogram models available for fitting
    variogram_dict = {
        "linear": variogram_models.linear_variogram_model,
        "linear-sill": variogram_models.linear_sill_variogram_model,
        "gaussian": variogram_models.gaussian_variogram_model,
        "spherical": variogram_models.spherical_variogram_model,
        "exponential": variogram_models.exponential_variogram_model,
        "hole-effect": variogram_models.hole_effect_variogram_model,
    }
    
    def __init__(self,xy,z):
        """
        Initialize a Semivariogram from sample points.

        Parameters
        ----------
        xy : n x 2 array-like
            x and y coordinates of the sample (experimental) points.
        z : array-like
            Attribute value measured at each sample point.

        Returns
        -------
        None.
        """

        if system != 'Darwin':  # macOS errors when writing the semivariogram log to a txt file
            Log('\nStarting semivariogram generation\n')


        # Build a pandas DataFrame holding every point pair
        self.var=pd.DataFrame().astype('float32')
        # Column with the pairwise distances (lag)
        self.var['lag']=spatial.distance.pdist(xy, metric='euclidean')
        # Column with the squared differences (raw semivariances)
        self.var['gamma']=[(y - x)**2 for x, y in it.combinations(z, 2)]

        # Minimum distance between sample points
        self.min_dist=self.var['lag'].min()
        # Maximum distance, used to derive the active distance
        self.max_dist=self.var['lag'].max()
        # Sample variance of the attribute
        self.sample_variance=z.var()

        # Sort by ascending distance; gamma follows the same ordering
        self.var=self.var.sort_values(by='lag',ignore_index=True) # reset the index after sorting
   
         
		
    def Exp_Semiv(self, dist_lag, active_dist):  
        
        """
        Build the experimental semivariogram from the sample points and their
        attribute values.

        Parameters
        ----------
        dist_lag : float
            Lag width (h) that defines the distance bins.
        active_dist : float
            Maximum distance to consider; pairs farther apart are discarded.

        Returns
        -------
        lag, gamma, npoints
            Mean distance per bin, the semivariance per bin, and the number of
            point pairs used to build each lag.
        """

        # Drop point pairs farther apart than the active distance
        remove_index=self.var[self.var['lag'] > active_dist ].index
        self.var=self.var.drop(remove_index)

        # Bin edges used to classify the distances
        bins=np.arange(self.min_dist,max(self.var['lag']), dist_lag)

        # Assign each distance to a bin
        ind = np.digitize(self.var['lag'],bins)

        # Mean distance within each bin
        lag=self.var['lag'].groupby(ind).mean()

        # Mean of the squared differences halved per bin -> Matheron estimator
        gamma=self.var['gamma'].groupby(ind).mean().div(2)

        # Number of point pairs in each lag
        npoints=self.var['lag'].groupby(ind).count()


        self.lag=lag.to_numpy()     # pandas Series -> numpy
        self.gamma=gamma.to_numpy() # pandas Series -> numpy


        return self.lag.astype('float32'),self.gamma.astype('float32'),npoints
        
    
    
    def Gamma(self,model,parameter):
        
        """
        Evaluate the theoretical semivariance from the lag vector (self.lag).

        Parameters
        ----------
        model : str
            Chosen semivariogram model: one of linear, linear-sill, spherical,
            gaussian, exponential, hole-effect.
        parameter : sequence
            Model parameters as [nugget, range, sill].

        Returns
        -------
        gammaT : ndarray
            Theoretical semivariance.
        rss : float
            Residual sum of squares.
        r2 : float
            Coefficient of determination.
        """

        #Nugget = self.models[self.model][0]
        #Range  = self.models[self.model][1]
        #Sill   = self.models[self.model][2]
        
        func=self.variogram_dict[model]
        
        gammaT=func(self.lag,parameter[0],parameter[1],parameter[2])
        
        rss=np.sum((self.gamma-gammaT)**2)
        tss=np.sum((self.gamma-np.mean(self.gamma))**2)
        
 
        return gammaT, rss, 1-(rss/tss)
        
        
    def Fit(self,list_model):
        
        """
        Fit the theoretical model(s) to the experimental lag and gamma.

        Parameters
        ----------
        list_model : list of str
            Models to fit: any of linear, linear-sill, spherical, gaussian,
            exponential, hole-effect.

        Returns
        -------
        dict
            One entry per model. The key is the model name; the value is the
            list [nugget, range, sill, residual_sum_of_squares, r2].
        """
        #Adjust the theoretical semivariogram model
        lag=self.lag
        gamma=self.gamma
        nlag=len(lag)
        
        
        #lag[1]=np.inf
        #gamma[2]=np.nan
        
        #Pick a random initial value for the nugget
        Nugget=(gamma[1]*lag[0]-gamma[0]*lag[1])/(lag[0]-lag[1])
        if Nugget<0: Nugget=gamma[0]
        #Pick a random initial value for the sill
        Sill=(gamma[nlag-3]+gamma[nlag-2]+gamma[nlag-1])/3.0             
        #kick the starting value for the range
        Range=lag[int(nlag/2)]
        
        #Array of Initial Values. Also used in Gold Rule Fit                                                            
        self.init_vals = [Nugget, Range, Sill]
        
        #define the maximum values
        maxlim=[max(gamma),max(lag),max(gamma)]
        
        #dictyonary for results
        dict_results={}
        
        #
        for model in list_model:

            if system != 'Darwin':  # macOS errors when writing the semivariogram log to a txt file
                Log('\n\nFor model: '+ model+'\n')

            check=True #option of curve_fit to check finite values

            func=self.variogram_dict[model]
            
            #First using Curve Fit and Check_Finite=True
            try:
                #

                if system != 'Darwin':  # macOS errors when writing the semivariogram log to a txt file

                    Log('Using Curve Fit with Check_Finite: '+ str(check))

                    Log('\nInitial guesses : Nugget: '+str(Nugget)+'  Sill: '+str(Sill)+ '  Range: '+str(Range))
    
                    Log('\nlag , Gamma')
                
                    for i in range(len(lag)): 
                        
                        Log (str(lag[i]) +',' +str(gamma[i]))

                #return Nugget, Range , Sill and estimated covariance (not used)
                [Nugget,Range,Sill], _ = curve_fit(func, lag, gamma,method='trf', check_finite = check, p0=self.init_vals ,bounds=(0, maxlim) )
         

            except Exception:

                
                '''
                Log('ValueError at Curve Fit:  ydata or xdata contain NaNs, or if incompatible options are used. Change Check for false')
                
                Log('\nChutes Iniciais : Nugget: '+str(Nugget)+'  Sill: '+str(Sill)+ '  Range: '+str(Range))

                Log('\nlag , Gamma')
                
                for i in range(len(lag)): Log (str(lag[i]) +',' +str(gamma[i]))

                try :
                    
                     check=False #option of curve_fit to check finite values
                     Log('Using Curve Fit with Check_Finite: '+ str(check))
                    
                     #return Nugget, Range , Sill and estimated covariance (not used)
                     [Nugget,Range,Sill], _ = curve_fit(func, lag, gamma,method='trf', check_finite = check, p0=self.init_vals ,bounds=(0, maxlim) )

                except ValueError:
                    Log('ValueError at Curve Fit :  ydata or xdata contain NaNs, or if incompatible options are used. Change to Golden Rule')
                    
                    
                    Nugget,Range,Sill=self.Gold_Rule(model)
                '''    

                    
            #except RuntimeError:

                if system != 'Darwin':  # macOS errors when writing the semivariogram log to a txt file    

                    Log('Error at Curve Fit: least-squares minimization fails. Change to Golden Rule')
                     
                    Log('Initial guesses : Nugget: '+str(Nugget)+' Sill: '+str(Sill)+ ' Range: '+str(Range))
                     
                    Log ('\nlag , Gamma')
                    
                    for i in range(len(lag)): 
                        
                        Log (str(lag[i]) +',' +str(gamma[i]))

                Nugget,Range,Sill = self.Gold_Rule(model)
              
          
            else:

                if system != 'Darwin':  # macOS errors when writing the semivariogram log to a txt file                    
                    Log('No error in Curve Fit')

            finally:

                # Residual sum of squares, where error = experimental gamma - fitted gamma
                _,rss,r2=self.Gamma(model,[Nugget,Range,Sill])
                dict_results [model]  = [Nugget,Range,Sill,rss,r2]
        
        if system != 'Darwin':  # macOS errors when writing the semivariogram log to a txt file    
            Log('\nFitting finished\n')

        return dict_results
    
    
    def gold(self,ivar,xlow, xhigh, model, x,  y, z, maxIt, es):
        
        fp = -1;
         
        # Initialization
        r = 0.618033989
        xl = xlow
        xu = xhigh
        iiter = 1
        d = r*(xu-xl)
        x1 = xl+d
        x2 = xu-d
          
        if 'x' in ivar:
            _,f1,_=self.Gamma(model,[x1,y,z])
            _,f2,_=self.Gamma(model,[x2,y,z])

           
        elif 'y' in ivar:
            _,f1,_=self.Gamma(model,[x,x1,z])
            _,f2,_=self.Gamma(model,[x,x2,z])
        
        elif 'z' in ivar:
            _,f1,_=self.Gamma(model,[x,y,x1])
            _,f2,_=self.Gamma(model,[x,y,x2])
            
            
            
        if (f1*fp > f2*fp) : xopt = x1
        else : xopt = x2
        
        
        while True:
            d = r*d
            xint = xu-xl
            
            if (f1*fp > f2*fp) :
                xl = x2
                x2 = x1
                x1 = xl+d
                f2 = f1
                
                if 'x' in ivar:
                     _,f1,_=self.Gamma(model,[x1,y,z])
                     
                elif 'y' in ivar:
                     _,f1,_=self.Gamma(model,[x,x1,z])
                     
                elif 'z' in ivar:
                     _,f1,_=self.Gamma(model,[x,y,x1])

            else:
                xu = x1
                x1 = x2
                x2 = xu-d
                f1 = f2
                
                if 'x' in ivar:
                     _,f2,_=self.Gamma(model,[x2,y,z])
                     
                elif 'y' in ivar:
                     _,f2,_=self.Gamma(model,[x,x2,z])
                     
                elif 'z' in ivar:
                     _,f2,_=self.Gamma(model,[x,y,x2])
                     
            iiter=iiter+1
            if (f1*fp > f2*fp) : xopt = x1
            else : xopt = x2
            
            # Check for stop
            if (xopt != 0.0) : ea = (1-r)*abs(xint/xopt)*100
            if (ea <= es or iiter >= maxIt) : break
        
        return xopt            

    def Gold_Rule(self,model):
        
       
        maxIt=25
        es=0.01
        imaxit = 25   # maximum iterations of the golden-section rule
        j = 1;
       
        lag=self.lag
        gamma=self.gamma
        nlag=len(lag)
      
        #Pick a random initial value for the nugget
        Nugget=self.init_vals[0]
        Range=self.init_vals[1]
        Sill=self.init_vals[2]

       
        # Residual sum of squares, where error = experimental gamma - fitted gamma
        _,fant,_=self.Gamma(model,[Nugget,Range,Sill])
        
        while True:
            ivar = 'x'
            xL=0.00001
            xU= (gamma[nlag-3]+gamma[nlag-2]+gamma[nlag-1])/3.0
            Nugget=self.gold(ivar, xL, xU, model, Nugget, Range, Sill, maxIt, es)
            
            #
            ivar = 'y'
            xL=0.00001
            xU=lag[nlag-1]
            Range=self.gold(ivar, xL, xU, model, Nugget, Range, Sill, maxIt, es)
            
               #
            ivar = 'z'
            xL=(gamma[0]+gamma[1])/2
            xU=1.5*(gamma[nlag-4]+gamma[nlag-3]+gamma[nlag-2]+gamma[nlag-1])/4.0
            Sill=self.gold(ivar, xL, xU, model, Nugget, Range, Sill, maxIt, es)
            
            
            if (fant !=0):
                j=j+1
                _,fxyz,_=self.Gamma(model,[Nugget,Range,Sill])
                error = 100 * abs((fant - fxyz) / fant);
                fant = fxyz;
                if ((j >= imaxit) or (error < es)) : break
                    
                   
        if system != 'Darwin':  # macOS errors when writing the semivariogram log to a txt file    
            Log("Fitted successfully using the Golden Rule")
        
        return Nugget,Range,Sill
    

