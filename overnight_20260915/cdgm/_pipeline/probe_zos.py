import clr
from pathlib import Path
ROOT=Path('D:\\_Camera\\LensRebuild\\SuperSymmarXL')
ZDIR=Path(r'C:\Program Files\Ansys Zemax OpticStudio 2023 R1.00')
clr.AddReference(str(ZDIR/'ZOSAPI_NetHelper.dll'))
import ZOSAPI_NetHelper
print('init', ZOSAPI_NetHelper.ZOSAPI_Initializer.Initialize(str(ZDIR)), flush=True)
clr.AddReference(str(ZDIR/'ZOSAPI.dll'))
clr.AddReference(str(ZDIR/'ZOSAPI_Interfaces.dll'))
import ZOSAPI as Z
conn=Z.ZOSAPI_Connection()
app=conn.CreateNewApplication()
print('app',app,'license',app.IsValidLicenseForAPI,flush=True)
sys=app.PrimarySystem
print('system',sys.SystemName,flush=True)
app.CloseApplication()
