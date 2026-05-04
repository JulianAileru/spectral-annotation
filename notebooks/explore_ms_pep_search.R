library(mspepsearchr)
setwd("/users/j/a/jaileru/spectral-annotation/")

poslib = "spectral_libraries/HMDB/NIST-MS-Positive/hmdb_experimental_P"
neglib = "spectral_libraries/HMDB/NIST-MS-Negative/hmdb_experimental_N"
query = "spectral_libraries/HMDB/QUERY/msms_spectrum.msp"
query = mspepsearchr::ReadMsp(query)

hitlist <- IdentitySearchMsMS(query,poslib)