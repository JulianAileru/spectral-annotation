library(mspepsearchr)
library(mssearchr)

setwd("C:/Users/jaileru/Projects/spectral-annotation")

poslib = "spectral_libraries/HMDB/NIST-MS-Positive/hmdb_experimental_P"
neglib = "spectral_libraries/HMDB/NIST-MS-Negative/hmdb_experimental_N"
query = "spectral_libraries/HMDB/QUERY/msms_spectrum.msp"
query = mssearchr::ReadMsp(query)

hitlist <- IdentitySearchMsMs(query,libraries = c(poslib,neglib))

                              