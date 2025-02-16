#!/usr/bin/env python

'''
*+
*  Name:
*     MATCHBEAM

*  Purpose:
*     Smooth a 450 um SCUBA-2 map to produce a map with the 850 um beam

*  Language:
*     python (2.7 or 3.*)

*  Description:
*     This script smooths the supplied 450 um SCUBA-2 map using a kernel
*     that results in the output map having the 850 um beam shape.
*     Optionally, the 450 um map can first be resampled onto the pixel
*     grid of a supplied reference map (see parameter REF).
*
*     The smoothing kernel is determined by creating two NDFs, one for
*     450 um and one for 850 um, each holding the two-component model
*     beam described in Dempsey et al 2018 (arxiv.org/abs/1301.3773).
*     A Wiener filter is then used to deconvolve the 850 model beam using
*     the 450 model beam as the PSF. The resulting deconvolved image is
*     then used as the smoothing kernel to smooth the supplied 450 um map
*     (after alignment with the referene NDF if a reference NDF was
*     supplied).

*  Usage:
*     matchbeam in out ref

*  ADAM Parameters:
*     GLEVEL = LITERAL (Read)
*        Controls the level of information to write to a text log file.
*        Allowed values are as for "ILEVEL". The log file to create is
*        specified via parameter "LOGFILE. ["NONE"]
*     ILEVEL = LITERAL (Read)
*        Controls the level of information displayed on the screen by the
*        script. It can take any of the following values (note, these values
*        are purposefully different to the SUN/104 values to avoid confusion
*        in their effects):
*
*        - "NONE": No screen output is created
*
*        - "CRITICAL": Only critical messages are displayed such as warnings.
*
*        - "PROGRESS": Extra messages indicating script progress are also
*        displayed.
*
*        - "ATASK": Extra messages are also displayed describing each atask
*        invocation. Lines starting with ">>>" indicate the command name
*        and parameter values, and subsequent lines hold the screen output
*        generated by the command.
*
*        - "DEBUG": Extra messages are also displayed containing unspecified
*        debugging information.
*
*        In adition, the glevel value can be changed by assigning a new
*        integer value (one of starutil.NONE, starutil.CRITICAL,
*        starutil.PROGRESS, starutil.ATASK or starutil.DEBUG) to the module
*        variable starutil.glevel. ["PROGRESS"]
*     IN = NDF (Read)
*        An NDF holding the input 450 um map.
*     OUT = NDF (Write)
*        An output NDF holding the smoothed 450 um map.
*     LOGFILE = LITERAL (Read)
*        The name of the log file to create if GLEVEL is not NONE. The
*        default is "<command>.log", where <command> is the name of the
*        executing script (minus any trailing ".py" suffix), and will be
*        created in the current directory. Any file with the same name is
*        over-written. []
*     MSG_FILTER = LITERAL (Read)
*        Controls the default level of information reported by Starlink
*        atasks invoked within the executing script. This default can be
*        over-ridden by including a value for the msg_filter parameter
*        within the command string passed to the "invoke" function. The
*        accepted values are the list defined in SUN/104 ("None", "Quiet",
*        "Normal", "Verbose", etc). ["Normal"]
*     REF = NDF (Read)
*        An optional reference NDF defining the pixel grid for the output
*        NDF. If a null (!) value is supplied, the supplied input NDF is
*        smoothed directly without first being resampled. This parameter
*        is useful if you want to be able to compare the output NDF
*        pixel-for-pixel with another map (for instance, a map with a
*        different pixel size). In such cases, the comparison map should
*        be supplied as the reference map. [!]
*     RETAIN = _LOGICAL (Read)
*        Should the temporary directory containing the intermediate files
*        created by this script be retained? If not, it will be deleted
*        before the script exits. If retained, a message will be
*        displayed at the end specifying the path to the directory. [FALSE]

*  Copyright:
*     Copyright (C) 2019 East Asian Observatory
*     All Rights Reserved.

*  Licence:
*     This program is free software; you can redistribute it and/or
*     modify it under the terms of the GNU General Public License as
*     published by the Free Software Foundation; either Version 2 of
*     the License, or (at your option) any later version.
*
*     This program is distributed in the hope that it will be
*     useful, but WITHOUT ANY WARRANTY; without even the implied
*     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
*     PURPOSE. See the GNU General Public License for more details.
*
*     You should have received a copy of the GNU General Public License
*     along with this program; if not, write to the Free Software
*     Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
*     02110-1301, USA.

*  Authors:
*     DSB: David S. Berry (EAO)
*     {enter_new_authors_here}

*  History:
*     13-DEC-2019 (DSB):
*        Original version
*-
'''

import math
import starutil
from starutil import invoke
from starutil import NDG
from starutil import Parameter
from starutil import ParSys
from starutil import msg_out
from starutil import get_task_par

#  Assume for the moment that we will not be retaining temporary files.
retain = 0

#  Do not create a log file by default. Setting parameter GLEVEL=ATASK
#  will cause a logfile to be produced.
starutil.glevel = starutil.NONE

#  A function to clean up before exiting. Delete all temporary NDFs etc,
#  unless the script's RETAIN parameter indicates that they are to be
#  retained. Also delete the script's temporary ADAM directory.
def cleanup():
   global retain
   if retain:
      msg_out( "Retaining temporary files in {0}".format(NDG.tempdir))
   else:
      NDG.cleanup()
   ParSys.cleanup()

#  A function to create an NDF holding a two-component beam shape, as
#  defined in Dempsey et al 2018, using the supplied parameter values.
def Beam( alpha, beta, thetaM, thetaS, pixsize ):

#  Create an image of the main beam using the supplied pixel size.
#  Centre the Gaussian at the centre of pixel (1,1) (i.e. pixel
#  coords (0.5,0.5) ). The Gaussian has a peak value of 1.0.
   main = NDG( 1 )
   invoke( "$KAPPA_DIR/maths exp=\"'exp(-4*pa*(fx*fx+fy*fy)/(fb*fb))'\" "
           "fx='xa-px' fy='xb-py' fb='pb/pp' pp={0} px=0.5 py=0.5 "
           "pa=0.6931472 pb={1} out={2} type=_double lbound=\[-63,-63\] "
           "ubound=\[64,64\]".format( pixsize, thetaM, main ))

#  Similarly create an image of the secondary beam.
   sec = NDG( 1 )
   invoke( "$KAPPA_DIR/maths exp=\"'exp(-4*pa*(fx*fx+fy*fy)/(fb*fb))'\" "
           "fx='xa-px' fy='xb-py' fb='pb/pp' pp={0} px=0.5 py=0.5 "
           "pa=0.6931472 pb={1} out={2} type=_double lbound=\[-63,-63\] "
           "ubound=\[64,64\]".format( pixsize, thetaS, sec ))

#  Combine them in the right proportions to make the total beam.
   total = NDG( 1 )
   invoke( "$KAPPA_DIR/maths exp="'pa*ia+pb*ib'" out={0} ia={1} ib={2} "
           "pa={3} pb={4}".format( total, main, sec, alpha, beta ) )

#  Ensure the total 450 beam has a total data sum of 1.0.
   invoke("$KAPPA_DIR/stats ndf={0}".format(total))
   sum = float( get_task_par( "total", "stats" ) )
   result = NDG( 1 )
   invoke( "$KAPPA_DIR/cdiv in={0} scalar={1} out={2}".
           format( total, sum, result ))

#  Return the final beam.
   return result



#  Catch any exception so that we can always clean up, even if control-C
#  is pressed.
try:

#  Declare the script parameters. Their positions in this list define
#  their expected position on the script command line. They can also be
#  specified by keyword on the command line. No validation of default
#  values or values supplied on the command line is performed until the
#  parameter value is first accessed within the script, at which time the
#  user is prompted for a value if necessary. The parameters "MSG_FILTER",
#  "ILEVEL", "GLEVEL" and "LOGFILE" are added automatically by the ParSys
#  constructor.
   params = []

   params.append(starutil.ParNDG("IN", "Input 450 um map",
                                 get_task_par("DATA_ARRAY","GLOBAL",
                                                        default=Parameter.UNSET),
                                 maxsize=1))
   params.append(starutil.ParNDG("OUT", "Output smoothed map", exists=False,
                                 maxsize=1))
   params.append(starutil.ParNDG("REF", "Reference map",maxsize=1,minsize=0,
                                 default=None, noprompt=True))
   params.append(starutil.Par0L("RETAIN", "Retain temporary files?", False,
                                 noprompt=True))

#  Initialise the parameters to hold any values supplied on the command
#  line.
   parsys = ParSys( params )

#  It's a good idea to get parameter values early if possible, in case
#  the user goes off for a coffee whilst the script is running and does not
#  see a later parameter prompt or error...

#  Get the input, output and reference NDFs.
   indf = parsys["IN"].value
   ondf = parsys["OUT"].value
   rndf = parsys["REF"].value

#  See if temp files are to be retained.
   retain = parsys["RETAIN"].value

#  Check the input NDF is a 450 um map.
   cval = starutil.get_fits_header( indf, "INSTRUME" )
   if cval == "SCUBA-2":
      cval = starutil.get_fits_header( indf, "FILTER" )
      if cval != "450":
         raise starutil.InvalidParameterError("Input NDF ({0}) does not "
                                    "contain 450 um data".format(indf) )
      else:
         invoke("$KAPPA_DIR/ndftrace ndf={0}".format(indf) )
         ndim = int( get_task_par( "ndim", "ndftrace" ))
         if ndim == 3:
            nz = int( get_task_par( "dims(3)", "ndftrace" ))
            if nz == 1:
               ndim = 2
         if ndim != 2:
            raise starutil.InvalidParameterError("Input NDF ({0}) does not "
                                 "contain a 2-dimensional image".format(indf) )
   else:
      raise starutil.InvalidParameterError("Input NDF ({0}) does not "
                                    "contain SCUBA-2 data".format(indf) )

#  Get the input pixel size.
   xsize = float(get_task_par( "FPIXSCALE(1)", "ndftrace" ))
   ysize = float(get_task_par( "FPIXSCALE(2)", "ndftrace" ))
   pixsize = math.sqrt( xsize*ysize )

#  If a reference NDF was supplied, get its pixel size.
   if rndf:
      msg_out( "Aligning input map with reference map")
      invoke("$KAPPA_DIR/ndftrace ndf={0}".format(rndf) )
      xsize = float(get_task_par( "FPIXSCALE(1)", "ndftrace" ))
      ysize = float(get_task_par( "FPIXSCALE(2)", "ndftrace" ))
      rpixsize = math.sqrt( xsize*ysize )

#  If the reference pixels are larger than the input pixels, we align
#  them by rebinning the input pixels into the output. Otherwise we
#  resample the output from the input.
      rebin = ( rpixsize > pixsize )
      temp = NDG(1)
      invoke("$KAPPA_DIR/wcsalign in={0} lbnd=! out={1} ref={2} "
             "conserve=no method=sincsinc params=\[2,0\] rebin={3}".
             format(indf,temp,rndf,rebin))

#  If no reference was supplied, use the input NDF as the aligned NDF.
   else:
      temp = indf
      rpixsize = pixsize

#  Remove any third pixel axis.
   aligned = NDG(1)
   invoke("$KAPPA_DIR/ndfcopy in={0} out={1} trim=yes".format(temp,aligned) )

#  Now create a pair of NDFs holding the expected model beam shape at
#  450 um and at 850 um. The expected beams are defined in Dempsey et al
#  2018.
   msg_out( "Creating smoothing kernel")
   b450 = Beam( 0.94, 0.06, 7.9, 25.0, rpixsize )
   b850 = Beam( 0.98, 0.02, 13.0, 48.0, rpixsize )

#  Deconvolve the 850 um beam using the 450 um beam as the PSF. The
#  resulting map is the kernel that smooths a 450 um map so that the
#  result has the 850 um beam.
   kernel = NDG( 1 )
   invoke( "$KAPPA_DIR/wiener in={0} psf={1} out={2} xcentre=1 ycentre=1".
           format( b850, b450, kernel ))

#  Use this kernel to smooth the aligned 450 um map.
   msg_out( "Smoothing using above kernel")
   invoke( "$KAPPA_DIR/convolve in={0} out={1} psf={2} xcentre=1 ycentre=1".
           format( aligned, ondf, kernel ))

#  Remove temporary files.
   cleanup()

#  If an Exception of any kind occurred, display the message but hide the
#  python traceback. To see the trace back, uncomment "raise" instead.
except Exception as err:
#  raise
   msg_out( err, level=starutil.NOTSET )
   print( "See the end of the log file ({0}) for further details.".format(starutil.logfile) )
   cleanup()

# This is to trap control-C etc, so that we can clean up temp files.
except:
   cleanup()
   raise

