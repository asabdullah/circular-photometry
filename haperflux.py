
# coding: utf-8

#  Do aperture photometry on a Healpix map with a circle of a given
#  radius, and subtracting the background in an annulus
#  Units are assumed to be mK_RJ and are converted to Jy
#
#
#  INPUTS
#
#  inmap               Healpix fits file or map array
#                      If an array, it assumed to be 'RING' ordering
#                      if ordering keyword not set
#
#  freq                Frequency (GHz) to allow conversion to Jy
#
#  res_arcmin          Angular resolution (arcmin FWHM) of the data
#                      This is needed for the error estimation
#                      and only needs to be approximate
#                      ( for noise_model=1 only )
#
#
#
#  lon                 Longitude of aperture (deg)
#
#  lat                 Latitude of aperture (deg)
#
#  aper_inner_radius   Inner radius of aperture (arcmin)
#
#  aper_outer_radius1  1st Outer radius of aperture beteween aperture
#                      and  b/g annulus (arcmin)
#                      Make this the same as the inner radius for
#                      single annulus with no gap
#
#  aper_outer_radius2  2nd Outer radius of aperture for b/g annulus (arcmin)
#
#  units               String defining units in the map
#                      Options include ['K','K_RJ', 'K_CMB', 'MJy/sr','Jy/pixel']
#                      m for milli and u for micro can also be used for
#                      K e.g. 'mK_RJ' or 'mK'
#                      Default is 'K_RJ'
#
#
#  OPTIONAL:-
#
#  column              This can be set to any integer which represents
#                      the column of the map (default is column=0)
#
#  dopol               If this keyword is set, then it will calculate the
#                      polarized intensity from columns 1 and 2 (Q and
#                      U) as PI=sqrt(Q^2+U^2) with *no noise bias* correction
#                      N.B. This overrides the column option
#
#  nested              If set, then the ordering is NESTED
#                      (default is to assume RING if not reading in a file)
#
#
#  noise_model         Noise model for estimating the uncertainty
#                      0 (DEFAULT) = approx uncertainty for typical/bg annulus aperture
#                      sizes (only approximate!).
#                      1 = assumes white uncorrelated noise (exact)
#                      and will under-estimate in most cases with real backgrounds!
#
#  centroid	      reproject the source using gnomdrizz and uses the centroid of the source instead of input coordinates
#                      0 (DEFAULT) = no centroiding is done
#  		      1 = centroiding performed using IDL code cntrd
#
#  OUTPUTS
#
#  fd                  Integrated flux density in aperture after b/g
#                      subtraction (Jy)
#
#  fd_err              Estimate of error on integrated flux density (Jy)
#
#
#  fd_bg               Background flux density estimate (Jy)
#
#
#
#  HISTORY
#
# 26-Jun-2010  C. Dickinson   1st go
#  25-Jul-2010  C. Dickinson   Added conversion option from T_CMB->T_RJ
#  25-Jul-2010  C. Dickinson   Added 2nd outer radius
#  26-Aug-2010  C. Dickinson   Added generic 'unit' option
#  02-Sep-2010  C. Dickinson   Tidied up the code a little
#  19-Oct-2010  C. Dickinson   Use ang2vec rather than long way around
#                              via the pixel number
#  20-Oct-2010  M. Peel        Fix MJy/Sr conversion; add aliases for
# 							  formats
# 							  excluding
# 							  underscores
#
#  10-Feb-2011  C. Dickinson   Added column option to allow polarization
#  16-Feb-2011  C. Dickinson   Added /dopol keyword for doing polarized intensity
#  12-Mar-2011  C. Dickinson   Added flexibility of reading in file or array
#  01-Jun-2011  C. Dickinson   Added noise_model option
#  10-Nov-2011  M. Peel        Adding AVG unit option.
#  20-Sep-2012  P. McGehee     Ingested into IPAC SVN, formatting changes
#  11-Apr-2016  A. Bell        Translated to Python
# ----------------------------------------------------------

"""
=====================================================
haperflux.py : Circular aperture photmetry
=====================================================

This module provides circular aperture photometry
functionality for Healpix maps.

- :func:'convertToJy' convert units to Janskys
- :func:'planckcorr' conversion factor between CMB_K and Jy
"""

import matplotlib
import numpy as np
import matplotlib.pyplot as plt
import healpy as hp
import healpy.projector as pro
import astropy.io.fits as fits
import sys
import math
from astropy.stats import mad_std
from astropy import units as u
from astropy.coordinates import SkyCoord

def planckcorr(freq):
    h = 6.62606957E-34
    k = 1.3806488E-23
    T = 2.725
    x = h*(freq*1e9)/k/T
    return (np.exp(x) - 1)**2/x**2/np.exp(x)


def convertToJy(units, thisfreq, npix=None, pix_area = None):

    # get conversion factors for an aperture to Jy/pix, from any of the following units:
    # Kelvin(RJ), Kelvin(CMB), MJy/sr, Average

    if pix_area != None and npix != None:
        print "Only one of npix or pix_area should be specified! Proceeding with npix."


    if pix_area == None:
        pix_area = 4.*np.pi / npix

    factor = 1.0

        if (units == 'K') or (units == 'K_RJ') or (units == 'KRJ'):
            factor = 2.*1381.*(thisfreq*1.0e9)**2/(2.997e8)**2 * pix_area

        elif (units == 'mK') or (units == 'mK_RJ') or (units == 'mKRJ'):
            factor = 2.*1381.*(thisfreq*1.0e9)**2/(2.997e8)**2 * pix_area / 1.0e3

        elif (units == 'uK') or (units == 'uK_RJ') or (units == 'uKRJ'):
            factor = 2.*1381.*(thisfreq*1.0e9)**2/(2.997e8)**2 * pix_area / 1.0e6

        elif (units == 'K_CMB') or (units == 'KCMB'):
            factor = 2.*1381.*(thisfreq*1.0e9)**2/(2.997e8)**2 * pix_area / planckcorr(thisfreq)

        elif (units == 'mK_CMB') or (units == 'mKCMB'):
            factor = 2.*1381.*(thisfreq*1.0e9)**2/(2.997e8)**2 * pix_area / 1.0e3 / planckcorr(thisfreq)

        elif (units == 'uK_CMB') or (units == 'uKCMB'):
            factor = 2.*1381.*(thisfreq*1.0e9)**2/(2.997e8)**2 * pix_area / 1.0e6 / planckcorr(thisfreq)

        elif (units == 'MJy/sr') or (units == 'MJY/SR') or (units == 'MjySr'):
            factor = pix_area * 1.0e6

        elif (units == 'Jy/pixel') or (units == 'JY/PIXEL') or (units == 'JY/PIX') or (units == 'JyPix'):
            factor = 1.0

        elif (units == 'average') or (units == 'avg') or (units == 'Average') or (units == 'AVG'):
            factor = 1.0 / float(ninnerpix)
        else:
            print "Invalid units specified! "

        return factor

def healpix_phot(inputlist, maplist, radius, rinner, router, galactic=True, decimal=True):
    ##Here is the "observation data structure", which just means "a bunch of details
    ## about the different all-sky data sources which could be used here.
    freqlist =     ['30','44','70','100','143','217','353','545','857','1874','2141','2998','3331','4612','4997','11992','16655','24983','33310']
    freqval =      [28.405889, 44.072241,70.421396,100.,143.,217.,353.,545.,857.,1874.,2141.,2998.,3331.,4612.,4997.,11992.,16655.,24983.,33310.]
    fwhmlist =     [33.1587,28.0852,13.0812,9.88,7.18,4.87,4.65,4.72,4.39,0.86,0.86,4.3,0.86,0.86,4,3.8,0.86,3.8,0.86] # fwhm in arcminutes
    band_names =   ["akari9", "iras12", "akari18","iras25","iras60","akari65","akari90","iras100","akari140","akari160","planck857", "planck545"]

    k0 = 1.0
    k1 = rinner/radius
    k2 = router/radius
    apcor = ((1 - (0.5)**(4*k0**2))-((0.5)**(4*k1**2) - (0.5)**(4*k2**2)))**(-1)

    # 'galactic' overrules 'decimal'
    if (galactic==True):
        dt=[('sname',np.dtype('S13')),('glon',np.float32),('glat',np.float32)]
        targets = np.genfromtxt(inputlist, delimiter=",",dtype=dt)

    ns = len(targets['glat'])

    fd3 = -1
    fd_err3 = -1

    fn = np.genfromtxt(maplist, delimiter=" ", dtype='str')
    nmaps = len(fn)
    ## Initialize the arrays which will hold the results
    fd_all = np.zeros((ns,nmaps))
    fd_err_all = np.zeros((ns,nmaps))
    fd_bg_all = np.zeros((ns,nmaps))

    # Start the actual processing: Read-in the maps.
    for ct2 in range(0,nmaps):
        xtmp_data, xtmp_head = hp.read_map(fn[ct2], h=True, verbose=False, nest=False)
        freq = dict(xtmp_head)['FREQ']
        units = dict(xtmp_head)['TUNIT1']
        freq_str = str(freq)
        idx = freqlist.index(str(freq))
        currfreq = int(freq)

        if (radius == None):
            radval = fwhmlist[idx]
        else:
            radval = radius


        for ct in range(0,ns):

            glon = targets['glon'][ct]
            glat = targets['glat'][ct]

            fd_all[ct,ct2], fd_err_all[ct,ct2], fd_bg_all[ct,ct2] = \
                haperflux(inmap= xtmp_data, freq= currfreq, lon=glon, lat=glat, \
                        res_arcmin= radius, aper_inner_radius=radius, aper_outer_radius1=rinner, \
                        aper_outer_radius2=router,units=units)

            if (np.isfinite(fd_err_all[ct,ct2]) == False):
                fd_all[ct,ct2] = -1
                fd_err_all[ct,ct2] = -1
            else:
                if radius==None:
                    fd_all[ct,ct2] = fd_all[ct,ct2]*apcor
                    fd_err_all[ct,ct2] = fd_err_all[ct,ct2]*apcor

    return fd_all, fd_err_all, fd_bg_all



def haperflux(inmap, freq, lon, lat, res_arcmin, aper_inner_radius, aper_outer_radius1, aper_outer_radius2, \
              units, fd=0, fd_err=0, fd_bg=0, column=0, dopol=False, nested=False, noise_model=0, centroid=False, arcmin=True):

    #check parameters
    if len(sys.argv) > 8:
        print ''
        print 'SYNTAX:-'
        print ''
        print 'haperflux(inmap, freq, res_arcmin, lon, lat, aper_inner_radius, aper_outer_radius1, aper_outer_radius2, units, fd, fd_err, fd_bg,column, noise_model, /dopol, /nested)'
        print ''
        exit()


    #set parameters
    inmap = inmap
    thisfreq = float(freq) # [GHz]
    lon = float(lon) # [deg]
    lat = float(lat) # [deg]
    aper_inner_radius  = float(aper_inner_radius)  # [arcmin]
    aper_outer_radius1 = float(aper_outer_radius1) # [arcmin]
    aper_outer_radius2 = float(aper_outer_radius2) # [arcmin]

    # Convert the apertures to radians, if given in arcminutes.
    #     The pixel-finder 'query_disc' expects radians:
    if arcmin== True:

        aper_inner_radius  = aper_inner_radius/60.*np.pi/180.  # [rad]
        aper_outer_radius1 = aper_outer_radius1/60.*np.pi/180. # [rad]
        aper_outer_radius2 = aper_outer_radius2/60.*np.pi/180. # [rad]

    # read in data
    s = np.size(inmap)

    if (s == 1):
        print "Filename given as input..."
        print "Reading HEALPix fits file into a numpy array"

        hmap,hhead = hp.read_map(inmap, hdu=1,h=True, nest=nested)

    if (s>1):
        hmap = inmap

    if (nested==False):
        ordering='RING'
    else:
        ordering ='NESTED'

    nside = np.sqrt(len(hmap)/12)
    if (round(nside,1)!=nside) or ((nside%2)!=0):
        print ''
        print 'Not a standard Healpix map...'
        print ''
        exit()


    npix = 12*nside**2
    ncolumn = len(hmap)

    # get pixels in aperture
    phi   = lon*np.pi/180.
    theta = np.pi/2.-lat*np.pi/180.
    vec0  = hp.ang2vec(theta, phi)

    ## Get the pixels within the innermost (source) aperture
    innerpix = hp.query_disc(nside=nside, vec=vec0, radius=aper_inner_radius, nest=nested)

    #Get the background ring pixel numbers"
    outerpix1 = hp.query_disc(nside=nside, vec=vec0, radius=aper_outer_radius1, nest=nested)


    ## Get the pixels within the outer-ring of the background annulus
    outerpix2 = hp.query_disc(nside=nside, vec=vec0, radius=aper_outer_radius2, nest=nested)



    # Identify and remove the bad pixels
    # In this scheme, all of the bad pixels should have been labeled with HP.UNSEEN in the HEALPix maps
    bad0 = np.where(hmap[innerpix] == hp.UNSEEN)

    innerpix_masked = np.delete(innerpix,bad0)
    ninnerpix = len(innerpix_masked)

    bad1 = np.where(hmap[outerpix1] == hp.UNSEEN)
    outerpix1_masked = np.delete(outerpix1,bad1)
    nouterpix1 = len(outerpix1_masked)

    bad2 = np.where(hmap[outerpix2] == hp.UNSEEN)
    outerpix2_masked = np.delete(outerpix2,bad2)
    nouterpix2 = len(outerpix2_masked)

    if (ninnerpix == 0) or (nouterpix1 == 0) or (nouterpix2 == 0):
        print ''
        print '***No good pixels inside aperture!***'
        print ''
        fd = np.nan
        fd_err = np.nan
        exit()

    innerpix  = innerpix_masked
    outerpix1 = outerpix1_masked
    outerpix2 = outerpix2_masked

    # find pixels in the annulus (between outerradius1 and outeradius2)
    # In other words, remove pixels of Outer Radius 2 that are enclosed within Outer Radius 1
    bgpix = np.delete(outerpix2, outerpix1)

    nbgpix = len(bgpix)

    factor = covnertToJy(units, thisfreq, npix)

        # Get pixel values in inner radius, converting to Jy/pix
        fd_jypix_inner = hmap[innerpix] * factor

        # sum up integrated flux in inner
        fd_jy_inner = np.sum(fd_jypix_inner)

        # same for outer radius but take a robust estimate and scale by area
        fd_jy_outer = np.median(hmap[bgpix]) * factor

        # subtract background
        fd_bg        = fd_jy_outer
        fd_bg_scaled = fd_bg*float(ninnerpix)
        fd           = fd_jy_inner - fd_bg_scaled

        if (noise_model == 0):

            Npoints = (pix_area*ninnerpix) /  (1.13*(float(res_arcmin)/60. *np.pi/180.)**2)
            Npoints_outer = (pix_area*nbgpix) /  (1.13*(float(res_arcmin)/60. *np.pi/180.)**2)
            fd_err = np.std(hmap[bgpix]) * factor * ninnerpix / math.sqrt(Npoints)

        if (noise_model == 1):
            #Robust sigma (median absolute deviation) noise model
            # works exactly for white uncorrelated noise only!

            k = np.pi/2.

            fd_err = factor * math.sqrt(float(ninnerpix) + (k * float(ninnerpix)**2/nbgpix)) * mad_std(hmap[bgpix])





    return fd, fd_err, fd_bg_scaled
