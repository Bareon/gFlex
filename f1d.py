from __future__ import division # No automatic floor division
from base import *


class F1D(Flexure):
  def initialize(self, filename):
    super(F1D, self).initialize(filename)
    if debug: print 'F1D initialized'

  def run(self):
    if self.method == 'FD':
      # Finite difference
      super(F1D, self).FD()
      self.method_func = self.FD
    elif self.method == 'FFT':
      # Fast Fourier transform
      super(F1D, self).FFT()
      self.method_func = self.FFT
    elif self.method == "SPA":
      # Superposition of analytical solutions
      super(F1D, self).SPA()
      self.method_func = self.SPA
    elif self.method == "SPA_NG":
      # Superposition of analytical solutions,
      # nonuniform points
      super(F1D, self).SPA_NG()
      self.method_func = self.SPA_NG
    else:
      print 'Error: method must be "FD", "FFT", or "SPA"'
      self.abort()

    if debug: print 'F1D run'
    self.method_func ()
    # self.plot() # in here temporarily

  def finalize(self):
    ### need work
    if debug: print 'F1D finalized'
        
    
  ########################################
  ## FUNCTIONS FOR EACH SOLUTION METHOD ##
  ########################################
  
  def FD(self):
    if self.plotChoice:
      self.gridded_x()
    dx4, D = self.elasprep(self.dx,self.Te,self.E,self.nu)
    self.coeff = self.coeff_matrix(D,self.drho,dx4,self.nu,self.g)
    self.w = self.direct_fd_solve(self.coeff,self.q0)
    print D.max()
    print self.nu
    print self.drho

  def FFT(self):
    if self.plotChoice:
      self.gridded_x()
    print "The fast fourier transform solution method is not yet implemented."
    
  def SPA(self):
    self.gridded_x()
    self.spatialDomainVars()
    self.spatialDomainGridded()

  def SPA_NG(self):
    self.spatialDomainVars()
    self.spatialDomainNoGrid()

  
  ######################################
  ## FUNCTIONS TO SOLVE THE EQUATIONS ##
  ######################################


  ## UTILITY
  ############

  def gridded_x(self):
    from numpy import arange
    self.nx = self.q0.shape[0]
    self.x = arange(0,self.dx*self.nx,self.dx)
    
  
  ## SPATIAL DOMAIN SUPERPOSITION OF ANALYTICAL SOLUTIONS
  #########################################################

  # SETUP

  def spatialDomainVars(self):
    self.D = self.E*self.Te**3/(12*(1-self.nu**2)) # Flexural rigidity
    self.alpha = (4*self.D/(self.drho*self.g))**.25 # 1D flexural parameter
    self.coeff = self.alpha**3/(8*self.D)


  # GRIDDED

  def spatialDomainGridded(self):
  
    from numpy import zeros, exp, sin, cos

    self.w = zeros(self.nx) # Deflection array
    
    for i in range(self.nx):
      # Loop over locations that have loads, and sum
      if self.q0[i]:
        dist = abs(self.x[i]-self.x)
        # -= b/c pos load leads to neg (downward) deflection
        self.w -= self.q0[i] * self.coeff * self.dx * exp(-dist/self.alpha) * \
          (cos(dist/self.alpha) + sin(dist/self.alpha))
    # No need to return: w already belongs to "self"
    

  # NO GRID

  def spatialDomainNoGrid(self):
  
    from numpy import exp, sin, cos, zeros
    
    # Reassign q0 for consistency
    #self.q0_with_locs = self.q0 # nah, will recombine later
    self.x = self.q0[:,0]
    self.q0 = self.q0[:,1]
    
    self.w = zeros(self.x.shape)
    print self.w.shape
    
    i=0 # counter
    for x0 in self.x:
      dist = abs(self.x-x0)
      self.w -= self.q0[i] * self.coeff * self.dx * exp(-dist/self.alpha) * \
        (cos(dist/self.alpha) + sin(dist/self.alpha))
      if i==10:
        print dist
        print self.q0
      i+=1 # counter

  ## FINITE DIFFERENCE
  ######################
  
  def elasprep(self,dx,Te,E=1E11,nu=0.25):
    """
    dx4, D = elasprep(dx,Te,E=1E11,nu=0.25)
    
    Defines the variables (except for the subset flexural rigidity) that are
    needed to run "coeff_matrix_1d"
    """
    dx4 = dx**4
    D = E*Te**3/(12*(1-nu**2))
    output = dx4, D
    return output

  def coeff_matrix(self,D,drho,dx4,nu=0.25,g=9.8):
    """
    coeff = coeff_matrix(D,drho,dx4,nu,g)
    where D is the flexural rigidity, nu is Poisson's ratio, drho is the  
    density difference between the mantle and the material filling the 
    depression, g is gravitational acceleration at Earth's surface (approx. 
    9.8 m/s), and dx4 is based on the distance between grid cells (dx).
    
    All grid parameters except nu and g are generated by the function
    varprep2d, located inside this module
    
    D must be one cell larger than q0, the load array.
  
    1D pentadiagonal matrix to solve 1D flexure with variable elastic 
    thickness via a Thomas algorithm (assuming that scipy uses a Thomas 
    algorithm).
    
    Uses the thin plate assumption, as do all of the methods here.
    
    Based on and translated in part from "flexvar.m", written in 2001 by Bob
    Anderson, which in turn is based on a code written by Laura Wallace
    
    Changes here include increased vectorization of operations (for speed) 
    and the use of sparse matrices (to reduce memory usage and unnecessary 
    tracking of zeros)
    """
    
    from numpy import vstack, array
    from scipy.sparse import dia_matrix

    print dx4

    # Diagonals, from left to right  
    l2 = D[:-2] / dx4
    l1 = -2 * (D[1:-1] + D[:-2]) / dx4
    c0 = ( (D[2:] + 4*D[1:-1] + D[:-2]) / dx4 ) + drho*g
    r1 = -2 * (D[1:-1] + D[2:]) / dx4
    r2 = D[2:] / dx4
    
    # Construct sparse array
    ncolsx = c0.shape[0]
    coeffs = vstack((l2,l1,c0,r1,r2))
    offsets = array([-2,-1,0,1,2])
    c = dia_matrix( (coeffs,offsets), shape = (ncolsx,ncolsx) )

    return c
    

  def direct_fd_solve(self,coeff,q0):
    """
    w = direct_fd_solve(coeff,q0)
      where coeff is the sparse coefficient matrix output from function
      coeff_matrix and q0 is the array of loads

    Sparse solver for one-dimensional flexure of an elastic plate
    """
    
    from scipy.sparse.linalg import spsolve
    from scipy.sparse import csr_matrix

    coeff = csr_matrix(coeff) # Needed for solution
    q0sparse = csr_matrix(-q0) # Negative so bending down with positive load,
                               # bending up with negative load (i.e. material
                               # removed)
                               # *self.dx
    w = spsolve(coeff,q0sparse)

    return w

