Homework 6:
Question 1 - Phase 1 - 5 went smoothly no issue, Part of the grill-me i did make a few minor requests. I ended up building it prior so when i added the next steps adding new skills it shows no plan but the pytest does say that everything is working.

Question 2 - two django that are used to complete the account security center is accouts/view.py and accounts/forms.py.
accounts/view.py
line 52 - is where you enter your email
line 66 - check inbox 
line 70 allow you to choose a new password


Question 3 

accounts/forms
line 49 - is the email form
line 58 - is for the new password form
line 387 - confirms email match
line 394 sends the link
line 444 saves and builds a link
there is another file token.py line 8 checks itself 

I added more options like not having staff take time to change or correct the password reset. I also added the option they can look up there username as well. 
** Learned that the accounts/forms isn't mine it is in Django own django/contrib/auth/forms.py and the token.py is also django's. that would make sense since i never made a auth pathway.

Question 4 - 
I dont have plans/account-security.md i believe AI said it was account-email. Let me see if i can get this fixed.




# Product Images - Questions

1. 
I didn't disagree, but it did point me to the thumbnails idea for the back office. This will help keep space down for "staff" and see the image is correct which is the best direction to go and ensure everything is listed correctly.

2.
A.  
image = models.ImageField(upload_to="products/", blank=True) ----> saves uploaded files into media/products
B.
<form method="post" enctype="multipart/form-data" class="mt-2 space-y-4">
  {% csrf_token %}
  {% for field in form %}
    {% include "products/partials/_field.html" %}
  {% endfor %}

enctype is needed to upload the image if it isn't working it only send file name but not the file.

3.
Lumin Drake is the product I created. The pathway the image is stored on {C:\Users\saman\cidm3312\thoughttronix-store - HW5\media\products\Lumin_Drake.jpg}. The value stored in the database for the image is {products/Lumin_Drake.jpg}. and the URL browser requests to display it shows {/media/products/Lumin_Drake.jpg (in full: http://127.0.0.1:8000/media/products/Lumin_Drake.jpg)}

Product --> Media ---> URL 
   the starting point is at product, the file is located in media, and url is how it ties it all together


****Best explaination in my words:
The image file is stored locally at media/products/lumin_drake.jpg. The base directory is governed by the media_root configs in config/settings.py (line144). The products/ folder inside media is determined by the upload_to="products/" directions set on the product's Imagefield in products/models.py (line 77). To prevent saving raw image in binary it stores the relative path string products/lumin_drake.jpg (strug) which is string value for the image column, that corresponds to the image field listed on the projuct model in products/models.py. Displaying the piscure is a request from the browser /media/products/lumin_drake.jpg. Django generates the url by prefixing the data path (products/lumin_drake.jpg) in the project media_url setting. It configured in config/settings.py. The media URL functions on the local server urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT) with help from config/urls.py (line22). which snippet the instructions for django dev server intercept /media requesting and corresponding physical file directly from directory specified by media_root, which is only active when debug= true is on.


***Claude helping me explain:
 Path on disk. The file is saved at  media\products\Lumin_Drake.jpg in your project folder. The setting that decides the folder is MEDIA_ROOT, defined in the file settings config/settings.py (line 144). The subfolder products/ comes from  upload_to="products/" on the field in the image field in products/models.py (line 77)duct.
2. Database value. The database stores the text  products/Lumin_Drake.jpg , not the picture itself. The field that stores it is  image (an ImageField), defined in products/models.py (right).
3. URL. The browser requests /media/products/Lumin_Drake.jpg. Django builds it by putting the setting  MEDIA_URL, which is "media/" in front of the database value, products/Lumin_Drake.jpg
4. Why it works on the dev server. The line  urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  in the file config/urls.py (line 22) adds a route that answers /media/ requests by  finding the file in the media folder (MEDIA_ROOT) and sending it back. It only works when DEBUG is on.


















Question 1 Answer:
Marking the product as featured in the admin interface is a true/fals logic that when check it displays the badge on the catoglog list. If you uncheck it, this would remove the badge stating featured. The logic is located in products --> 0003_product_is_featured.py file. This is  migrated which works with the catalog_complete file also. 

Question 2 Answer:
Once you start your server, there are two ways to check first is the admin side going to product and clickin on one of them to edit. In there next to availiablity is were the feature checkbox is listed. If you than click on that and open the main page for the catagolg you can see it listed if it isn't on the main page but it would provide the badge next to its name. 

Question 3 Answer:
This time around no trouble, just more so the understanding of the instructions and which file to use. 


-------------------------------------------------------------------------------------------------------

Homework 4 Answers:

#1.
One question was that lead to important design decision was actually me reviewing it and it swapped out the coupon but didn't show it. Adding the swap by fazing the expired coupon out and showing what was swapped with is a huge win for when your in the cart. There wasn't any questions i didn't understand, i was just more amazed and at ahh with how fast it was added and before that how quickly it was to setup. 

#2.
The change was helpful as i talked about it above, it provided the user when checking the cart what coupon they typed in has expired and showing the newest current one active so they can still get the discount. I choose this feature because so many times i have checked out and it just says cant add and than you have nothing. Thinking about it now you can always do a smaller coupon if they didn't use the previous one so they get a coupon to work still but this isn't an actual business so i suppose i can spurge and spoil the customers. That would be a different workaround tho because it would remove the swapping and just replace it with an internal set coupon that wouldn't be questions more of a loyality option for coming back. 