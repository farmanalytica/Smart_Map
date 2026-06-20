# coding: utf-8
"""
/***************************************************************************
# File: kriging.py

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

import numpy as np
from scipy.spatial.distance import cdist
from . import variogram_models
import matplotlib.path as mplPath
from scipy.spatial import cKDTree
import scipy.linalg.lapack



class OrdinaryKriging:
    

    eps = 1.0e-10  # Cutoff below which a distance is treated as zero
    # Theoretical semivariogram models available for kriging
    variogram_dict = {
        "linear": variogram_models.linear_variogram_model,
        "linear-sill": variogram_models.linear_sill_variogram_model,
        "gaussian": variogram_models.gaussian_variogram_model,
        "spherical": variogram_models.spherical_variogram_model,
        "exponential": variogram_models.exponential_variogram_model,
        "hole-effect": variogram_models.hole_effect_variogram_model,
    }

    def __init__(
        self,
        xy,
        z,
        variogram_model,
        variogram_parameters):
        
        """
        Initialize an OrdinaryKriging interpolator.

        Parameters
        ----------
        xy : n x 2 array-like
            x and y coordinates of the sample (experimental) points.
        z : array-like
            Attribute value measured at each sample point.
        variogram_model : str
            Name of the theoretical semivariogram model (see variogram_dict).
        variogram_parameters : sequence
            Model parameters as [nugget, range, sill].

        Returns
        -------
        None.
        """
        
        self.x=xy.iloc[:,0]
        self.y=xy.iloc[:,1]
        self.z=z.to_numpy()
        
        
        
        self.variogram_model_parameters=variogram_parameters
        
        # Set up variogram model and parameters
        self.variogram_model = variogram_model
        # Resolve the semivariogram function to evaluate
        self.variogram_function = self.variogram_dict[self.variogram_model]

        
   
    def Grid (self,pixel_x,pixel_y,has_contour,points):
        
        """
        Build the grid of points where interpolation will be performed.

        Parameters
        ----------
        pixel_x : float
            Grid cell (pixel) size along x.
        pixel_y : float
            Grid cell (pixel) size along y.
        has_contour : bool
            Whether a boundary contour has been defined.
        points : n x 2 array-like
            Contour vertices when has_contour is True, otherwise the sample
            points. Column 0 is X, column 1 is Y.

        Returns
        -------
        n x 2 ndarray
            When a contour is defined, only the grid points inside it. Otherwise
            every grid point in the bounding rectangle from (xmin, ymin) to
            (xmax, ymax).
        """

        # Bounding box of the input points
        x_min = points.iloc[:,0].min()
        x_max = points.iloc[:,0].max()

        y_min = points.iloc[:,1].min()
        y_max = points.iloc[:,1].max()

        # Grid axes. arange excludes the stop value, so x_max/y_max are not reached
        gridx = np.arange(x_min, x_max, pixel_x)
        gridy = np.arange(y_min, y_max, pixel_y)


        # Build the contour polygon once, if a contour was defined
        if has_contour:
            contours = mplPath.Path(np.array(points))

        # Collect grid points as an n x 2 list (cell centers)
        gridxy=[]
        # Iterate over every (i, j) cell of the grid
        for i in gridx:
            for j in gridy:
                # Keep the cell center only if it falls inside the contour
                if has_contour:
                    if contours.contains_point((i+(pixel_x/2),j-(pixel_y/2))):
                        gridxy.append([i+(pixel_x/2),j-(pixel_y/2)])

                # No contour: keep every cell center
                else :
                    gridxy.append([i+(pixel_x/2),j-(pixel_y/2)])


        # n x 2 array of grid points (inside the contour when defined)
        return np.array(gridxy)

    def _get_kriging_matrix(self, n):
        """
        Assemble the ordinary kriging matrix (modified from PyKrige).

        Builds the (n+1) x (n+1) kriging matrix C holding the covariance
        between every pair of sample points, plus the Lagrange-multiplier
        row/column that enforces unbiasedness.
        """
        # Stack coordinates into an n x 2 array
        xy = np.concatenate((self.x.to_numpy(float)[:, np.newaxis], self.y.to_numpy(float)[:, np.newaxis]), axis=1 )

        self.xy=xy
        # Pairwise distance matrix, n x n
        d = cdist(xy, xy, "euclidean")
        #
        a = np.zeros((n + 1, n + 1))
        nug,rang_,sill=self.variogram_model_parameters
        a[:n, :n] = -self.variogram_function(d,nug,rang_,sill)
        np.fill_diagonal(a, 0.0)
        a[n, :] = 1.0
        a[:, n] = 1.0
        a[n, n] = 0.0

        return a

 
    
    def _exec_loop(self,a_all,xypts,n):
            
        """
        Compute the interpolated value and the estimation standard deviation
        at every grid point (modified from PyKrige).

        Parameters
        ----------
        a_all : (n+1) x (n+1) ndarray
            Covariance matrix between all sample points.
        xypts : array-like
            Coordinates of the grid points to interpolate.
        n : int
            Number of sample points.

        Returns
        -------
        zvalues, sigma
            Interpolated values and their estimation standard deviations.
        """

        # Number of grid points
        npt= len(xypts)
        # Output buffers
        zvalues=np.zeros(npt)
        sigmasq=np.zeros(npt)

        # Build a spatial search tree over the sample points.
        # self.xy (set in _get_kriging_matrix) is the n x 2 sample-point array.
        tree = cKDTree(self.xy)


        # p=2 -> Euclidean distance.
        # distance_upper_bound -> max radius to search for neighbors.
        # When fewer than k neighbors lie within the radius, query() pads the
        # index array with n (an out-of-range sentinel) and distance inf.

        #dist_all,ids_all=tree.query(xypts,k=self.n_closest_points,p=2,
        #                distance_upper_bound=self.radius, n_jobs=-1)     # for QGIS < 3.28
        #dist_all,ids_all=tree.query(xypts,k=self.n_closest_points,p=2,
        #                distance_upper_bound=self.radius, workers=-1)    # for QGIS >= 3.28

        dist_all,ids_all=tree.query(xypts,k=self.n_closest_points,p=2,
                        distance_upper_bound=self.radius)                 # workers parameter dropped


        # Fallback query for the 4 nearest neighbors, ignoring the search radius.
        # Cheaper, used when the radius search returns fewer than 4 neighbors.
        #dist_4n,ids_4n=tree.query(xypts,k=4,p=2,workers=-1)
        dist_4n,ids_4n=tree.query(xypts,k=4,p=2)                         # workers parameter dropped


        # For each grid point
        for i in range(npt):

            # Neighbor ids for grid point i
            ids=ids_all[i]

            # Distances to those neighbors
            dist=dist_all[i]

            # Drop the padded sentinels (id == n) added when fewer than k
            # neighbors were found within the radius.
            idx_del = np.argwhere(ids == n)
            dist = np.delete(dist, idx_del)
            ids = np.delete(ids, idx_del)

            # Number of neighbors actually found
            n_neig=len(ids)


            # If fewer than 4, fall back to the 4 nearest (radius ignored)
            if n_neig<4:
                 n_neig=4
                 # Reuse the precomputed 4-nearest results
                 ids=ids_4n[i]
                 dist=dist_4n[i]


            # Select, from matrix a (C), the covariances among the neighbors
            # of point i (plus the Lagrange row/column).
            a_selector = np.concatenate((ids, np.array([a_all.shape[0] - 1])))
            a = a_all[a_selector[:, None], a_selector]

            # Distances at or below the cutoff (eps) are treated as zero
            if np.any(np.absolute(dist) <= self.eps):
                zero_value = True
                zero_index = np.where(np.absolute(dist) <= self.eps)
            else:
                 zero_index = None
                 zero_value = False
         
            b = np.zeros((n_neig + 1, 1))
            nug,rang_,sill=self.variogram_model_parameters
            b[:n_neig, 0] = -self.variogram_function(dist, nug,rang_,sill)
            if zero_value:
                b[zero_index[0], 0] = 0.0
            b[n_neig, 0] = 1.0
            
            # Determinant of the kriging matrix
            det_a = np.linalg.det(a)
            # A zero determinant means the matrix is singular and cannot be
            # inverted, which would raise numpy.linalg.LinAlgError: Singular
            # matrix. Fall back to a least-squares solution in that case.
            # https://stackoverflow.com/questions/64527098/numpy-linalg-linalgerror-singular-matrix-error-when-trying-to-solve
            if det_a == 0:
              x = np.linalg.lstsq(a, b, rcond=None)[0]
            else:
              #x = np.linalg.lstsq(a, b, rcond=None)[0]
              x = scipy.linalg.solve(a, b)

            zvalues[i] = x[:n_neig, 0].dot(self.z[ids])
            sigmasq[i] = -x[:, 0].dot(b[:, 0])
   
         
        return zvalues, np.sqrt(sigmasq)

 
    def execute(
        self,
        xypoints,
        n_closest_points,
        radius):
        
        """
        Run the ordinary kriging interpolation.

        Parameters
        ----------
        xypoints : array-like
            x and y coordinates of the grid points to interpolate.
        n_closest_points : int
            Number of neighbors to use in the interpolation.
        radius : float
            Search radius for neighbors.

        Notes
        -----
        The search radius takes priority. If more neighbors than
        n_closest_points fall within the radius, only n_closest_points are
        used; otherwise all neighbors found are used, with a minimum of 4.

        Returns
        -------
        zvalues : ndarray
            Values interpolated by ordinary kriging.
        sigmasq : ndarray
            Estimation standard deviation associated with each value.
        """
        self.radius=radius
        self.n_closest_points=n_closest_points


        # Number of sample points
        n = len(self.x)

        # Matrix C for kriging (covariance between all sample points)
        a = self._get_kriging_matrix(n)

        # Interpolate at every grid point
        zvalues, sigmasq = self._exec_loop(a, xypoints,n)
 

        return zvalues, sigmasq